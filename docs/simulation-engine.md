# Simulation Engine

## Overview

The simulation engine is a discrete-event simulation (DES) built on [SimPy](https://simpy.readthedocs.io/). Hospital operations are modelled as concurrent processes competing for shared resources. Time advances in discrete "steps" — callers choose how many simulated minutes to advance per API call.

---

## Configuration

All parameters are defined in `SimulationConfig` (`backend/app/simulation/config.py`).

| Parameter | Default | Description |
|-----------|---------|-------------|
| `seed` | 42 | NumPy RNG seed for determinism |
| `icu_beds` | 20 | Total ICU capacity |
| `regular_beds` | 80 | Regular ward capacity |
| `num_doctors` | 15 | Available doctors (priority resource) |
| `num_nurses` | 40 | Available nurses (priority resource) |
| `num_equipment_units` | 30 | Shared equipment units |
| `mean_inter_arrival_minutes` | 10.0 | Exponential inter-arrival time (~6 pt/hr) |
| `mean_triage_duration` | 5.0 | Minutes to complete triage |
| `mean_regular_treatment` | 120.0 | Minutes for regular ward treatment |
| `mean_icu_duration` | 2880.0 | Minutes in ICU (2 days) |
| `prob_icu_transfer` | 0.05 | Mid-treatment ICU transfer probability |
| `spike_interval_mean` | 480.0 | Minutes between emergency spikes |
| `spike_patient_min` | 3 | Minimum patients per spike |
| `spike_patient_max` | 10 | Maximum patients per spike |
| `shortage_interval_mean` | 1440.0 | Minutes between staff shortages |
| `shortage_fraction` | 0.30 | Fraction of staff unavailable |
| `shortage_duration_mean` | 120.0 | Duration of staff shortage |
| `default_step_minutes` | 60.0 | Default step size (1 hour) |
| `max_simulation_time` | 10080.0 | Simulation cap (1 week) |

Override any parameter via the `POST /simulation/start` body:

```json
POST /api/v1/simulation/start
{
  "config": {
    "seed": 99,
    "icu_beds": 30,
    "num_doctors": 20,
    "mean_inter_arrival_minutes": 7.0
  }
}
```

---

## SimPy Processes

Five concurrent SimPy generator processes run inside the environment:

### 1. Patient Arrival Process
```
patient_arrival_process(env, state, resources, event_log, config, rng)
```
- Samples inter-arrival time from `Exponential(mean_inter_arrival_minutes)`
- Each arrival triggers the full patient journey (see below)
- Logs `PATIENT_ARRIVED` event with triage level and patient ID

### 2. Emergency Spike Process
```
emergency_spike_process(env, state, resources, event_log, config, rng)
```
- Fires every `Exponential(spike_interval_mean)` simulated minutes
- Injects 3–10 extra patients with skewed severity (more CRITICAL/HIGH)
- Logs `EMERGENCY_SPIKE` event with patient count

### 3. Staff Shortage Process
```
staff_shortage_process(env, state, resources, event_log, config, rng)
```
- Fires every `Exponential(shortage_interval_mean)` simulated minutes
- Temporarily reduces SimPy resource capacity for doctors and nurses
- Logs `STAFF_SHORTAGE` and `STAFF_RESTORED` events

### 4. Regular Treatment Journey
```
_regular_treatment(patient, env, state, resources, event_log, config, rng)
```
Sequence:
1. Request `doctor` (PriorityResource, priority = triage severity)
2. Triage: hold for `Exponential(mean_triage_duration)` minutes → `TRIAGE_COMPLETE`
3. Assign doctor → `DOCTOR_ASSIGNED`, request `regular_bed`
4. Treatment: hold for `Exponential(mean_regular_treatment)` minutes → `TREATMENT_STARTED`
5. Mid-treatment ICU transfer check (probability `prob_icu_transfer`)
6. Outcome: discharge or death based on mortality probability → `DISCHARGE` or `PATIENT_DEATH`

### 5. ICU Journey
```
_icu_journey(patient, env, state, resources, event_log, config, rng)
```
Sequence:
1. Request `icu_bed` resource
2. ICU treatment: hold for `Exponential(mean_icu_duration)` minutes
3. Outcome: discharge or death (mortality ×1.5 multiplier for ICU patients)

---

## Triage System

`TriagePolicy` assigns one of four levels using weighted random selection:

| Level | Default Weight | Emergency Weight | Priority |
|-------|---------------|------------------|----------|
| CRITICAL | 0.05 | 0.175 (×3.5) | 0 (highest) |
| HIGH | 0.20 | 0.300 (×1.5) | 1 |
| MEDIUM | 0.45 | 0.450 (×1.0) | 2 |
| LOW | 0.30 | 0.060 (×0.2) | 3 (lowest) |

Doctors and nurses are modelled as `simpy.PriorityResource` — CRITICAL patients preempt lower-priority patients in the queue.

---

## Event Types

| Event | Trigger | Key Metadata |
|-------|---------|-------------|
| `patient_arrived` | New patient enters system | `patient_id`, `triage_level`, `is_emergency` |
| `triage_complete` | Triage assessment finished | `patient_id`, `triage_level`, `duration_minutes` |
| `doctor_assigned` | Doctor allocated to patient | `patient_id`, `doctor_id` |
| `treatment_started` | Bed acquired, treatment begins | `patient_id`, `bed_type` |
| `icu_transfer` | Patient moved to ICU | `patient_id`, `reason` |
| `discharge` | Patient leaves hospital | `patient_id`, `length_of_stay_minutes` |
| `patient_death` | Simulation mortality event | `patient_id`, `triage_level` |
| `emergency_spike` | Burst arrival event | `patient_count`, `severity_mix` |
| `staff_shortage` | Capacity reduction begins | `fraction_reduced`, `affected_roles` |
| `staff_restored` | Capacity restored | `duration_minutes` |
| `simulation_started` | Engine initialised | `seed`, `config_summary` |
| `simulation_stepped` | Step completed | `step_number`, `step_minutes` |
| `simulation_reset` | Engine torn down | — |

---

## State Tracking

`HospitalStateManager` maintains live counters across all events:

| Metric | Source |
|--------|--------|
| `icu_occupancy` | Incremented on ICU transfer, decremented on discharge/death |
| `regular_bed_occupancy` | Incremented on treatment start, decremented on outcome |
| `emergency_queue_length` | Incremented on arrival, decremented on triage |
| `staff_availability` | Fraction of max staff currently active |
| `doctor_workload` | `regular_bed_occupancy / available_doctors` (capped 1.0) |
| `nurse_workload` | `(icu + ward) / available_nurses` (capped 1.0) |
| `patient_throughput` | Running discharge count |
| `equipment_utilization` | `in_use / total_equipment` |
| `active_patients_count` | Live patient dict size |
| `discharged_count` | Cumulative discharges |
| `death_count` | Cumulative simulation deaths |

---

## Determinism and Replay

The engine is designed for **deterministic replay**:

1. The same `seed` always produces the same sequence of random variates
2. The `EventLog` is append-only — it can be persisted and re-indexed
3. Starting a new engine with the same seed and config recreates the identical trajectory
4. The Replay Store (Phase 6) persists runs step-by-step for cursor-based playback without re-running the engine

---

## Benchmarks (seed=42)

| Duration | Patients | Discharges | Deaths | Wall Time |
|----------|----------|------------|--------|-----------|
| 10 hours (5 × 2hr) | ~63 | ~44 | 1 | <100ms |
| 1 week (168 × 1hr) | ~1,000+ | ~700+ | ~15 | <2s |

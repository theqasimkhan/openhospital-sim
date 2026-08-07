"""
SimPy generator processes that model patient flow through the hospital.

Process hierarchy
─────────────────
patient_arrival_process  ──spawns──► patient_journey
                                         ├── _icu_journey         (direct ICU)
                                         └── _regular_treatment   (ward → maybe ICU)

emergency_spike_process  ──spawns──► patient_journey (is_emergency=True)

staff_shortage_process   ──adjusts resources capacity──► resolves after duration

All state mutations go through HospitalStateManager.
All significant transitions are recorded in EventLog.
"""
from __future__ import annotations

import numpy as np
import simpy

from app.simulation.config import SimulationConfig
from app.simulation.events import EventLog, SimEventType
from app.simulation.policies import (
    admission_policy,
    discharge_policy,
    triage_policy,
    triage_priority,
)
from app.simulation.resources import HospitalResources
from app.simulation.state import (
    HospitalStateManager,
    Patient,
    PatientStatus,
    TriageLevel,
)

# ── Patient journey ────────────────────────────────────────────────────────────

def patient_journey(
    env: simpy.Environment,
    patient: Patient,
    state: HospitalStateManager,
    resources: HospitalResources,
    event_log: EventLog,
    config: SimulationConfig,
    rng: np.random.Generator,
) -> simpy.events.ProcessGenerator:
    """
    Full patient lifecycle: triage → treatment (ward or ICU) → outcome.
    This is a SimPy generator process.
    """
    # ── Triage ────────────────────────────────────────────────────────────────
    state.move_to_triage(patient)

    triage_duration = rng.exponential(config.triage_duration_mean)
    yield env.timeout(triage_duration)

    level = triage_policy.assess(rng, config, is_emergency=patient.is_emergency)
    state.complete_triage(patient, level, env.now)
    event_log.record(
        env.now,
        SimEventType.TRIAGE_COMPLETE,
        patient.id,
        triage_level=level.value,
        is_emergency=patient.is_emergency,
    )

    # ── Routing decision ──────────────────────────────────────────────────────
    if admission_policy.needs_direct_icu(level, rng):
        yield env.process(
            _icu_journey(env, patient, state, resources, event_log, config, rng)
        )
    else:
        yield env.process(
            _regular_treatment(env, patient, state, resources, event_log, config, rng)
        )


def _regular_treatment(
    env: simpy.Environment,
    patient: Patient,
    state: HospitalStateManager,
    resources: HospitalResources,
    event_log: EventLog,
    config: SimulationConfig,
    rng: np.random.Generator,
) -> simpy.events.ProcessGenerator:
    """
    Patient treated in the regular ward.
    Acquires: doctor (priority) + regular bed → treats → outcome.
    """
    priority = triage_priority(patient.triage_level or TriageLevel.MEDIUM)
    needs_icu_after = False

    with resources.doctors.request(priority=priority) as doc_req:
        yield doc_req

        doctor_id = f"DR-{(resources.doctors.count % config.num_doctors) + 1:03d}"
        state.assign_doctor(patient, doctor_id, env.now)
        event_log.record(
            env.now,
            SimEventType.DOCTOR_ASSIGNED,
            patient.id,
            doctor_id=doctor_id,
            triage_level=patient.triage_level.value if patient.triage_level else None,
        )

        with resources.regular_beds.request() as bed_req:
            yield bed_req

            state.start_treatment(patient, env.now)
            event_log.record(
                env.now,
                SimEventType.TREATMENT_STARTED,
                patient.id,
                location="regular_ward",
            )

            treatment_duration = rng.exponential(config.treatment_duration_mean)
            yield env.timeout(treatment_duration)

            # ── Outcome at end of regular treatment ───────────────────────────
            tl = patient.triage_level or TriageLevel.MEDIUM

            if discharge_policy.outcome_is_death(tl, in_icu=False, rng=rng, config=config):
                state.mark_deceased(patient, env.now)
                event_log.record(
                    env.now, SimEventType.PATIENT_DEATH, patient.id,
                    location="regular_ward",
                    triage_level=tl.value,
                )

            elif admission_policy.needs_icu_transfer(tl, rng, config):
                # Release regular bed resources before acquiring ICU
                state.release_from_regular_ward(patient)
                needs_icu_after = True
                # regular bed SimPy resource released as `with` exits below

            else:
                state.discharge_patient(patient, env.now)
                event_log.record(
                    env.now, SimEventType.DISCHARGE, patient.id,
                    location="regular_ward",
                    triage_level=tl.value,
                    length_of_stay=patient.length_of_stay,
                )
        # regular bed released here by SimPy
    # doctor released here by SimPy

    if needs_icu_after:
        event_log.record(
            env.now, SimEventType.ICU_TRANSFER, patient.id,
            reason="deterioration",
        )
        yield env.process(
            _icu_journey(env, patient, state, resources, event_log, config, rng)
        )


def _icu_journey(
    env: simpy.Environment,
    patient: Patient,
    state: HospitalStateManager,
    resources: HospitalResources,
    event_log: EventLog,
    config: SimulationConfig,
    rng: np.random.Generator,
) -> simpy.events.ProcessGenerator:
    """
    Patient admitted to ICU.
    Acquires: ICU bed → treats → outcome.
    """
    with resources.icu_beds.request() as icu_req:
        yield icu_req

        state.transfer_to_icu(patient, env.now)
        if patient.status == PatientStatus.IN_ICU:
            # Only log if not already logged as part of deterioration path
            event_log.record(
                env.now,
                SimEventType.ICU_TRANSFER,
                patient.id,
                reason="direct_admission",
                triage_level=patient.triage_level.value if patient.triage_level else None,
            )

        icu_duration = rng.exponential(config.icu_treatment_duration_mean)
        yield env.timeout(icu_duration)

        tl = patient.triage_level or TriageLevel.HIGH
        if discharge_policy.outcome_is_death(tl, in_icu=True, rng=rng, config=config):
            state.mark_deceased(patient, env.now)
            event_log.record(
                env.now, SimEventType.PATIENT_DEATH, patient.id,
                location="icu",
                triage_level=tl.value,
            )
        else:
            state.discharge_patient(patient, env.now)
            event_log.record(
                env.now, SimEventType.DISCHARGE, patient.id,
                location="icu",
                triage_level=tl.value,
                length_of_stay=patient.length_of_stay,
            )
    # ICU bed released here by SimPy


# ── Arrival process ────────────────────────────────────────────────────────────

def patient_arrival_process(
    env: simpy.Environment,
    state: HospitalStateManager,
    resources: HospitalResources,
    event_log: EventLog,
    config: SimulationConfig,
    rng: np.random.Generator,
) -> simpy.events.ProcessGenerator:
    """
    Continuously generates patients at exponentially-distributed intervals.
    """
    counter = 0
    while True:
        inter_arrival = rng.exponential(config.mean_inter_arrival_minutes)
        yield env.timeout(inter_arrival)

        counter += 1
        patient = Patient(
            id=f"PAT-{counter:06d}",
            arrival_time=env.now,
            is_emergency=False,
        )
        state.add_patient(patient)
        event_log.record(
            env.now,
            SimEventType.PATIENT_ARRIVED,
            patient.id,
            is_emergency=False,
        )
        env.process(
            patient_journey(env, patient, state, resources, event_log, config, rng)
        )


# ── Emergency spike process ────────────────────────────────────────────────────

def emergency_spike_process(
    env: simpy.Environment,
    state: HospitalStateManager,
    resources: HospitalResources,
    event_log: EventLog,
    config: SimulationConfig,
    rng: np.random.Generator,
) -> simpy.events.ProcessGenerator:
    """
    Generates sudden bursts of emergency patients at random intervals.
    """
    spike_counter = 0
    patient_counter = 0

    while True:
        interval = rng.exponential(config.spike_interval_mean)
        yield env.timeout(interval)

        spike_counter += 1
        spike_size = int(rng.integers(config.spike_size_min, config.spike_size_max + 1))

        event_log.record(
            env.now,
            SimEventType.EMERGENCY_SPIKE,
            patient_id=None,
            spike_number=spike_counter,
            spike_size=spike_size,
        )

        for i in range(spike_size):
            patient_counter += 1
            patient = Patient(
                id=f"EMG-{spike_counter:04d}-{i:03d}",
                arrival_time=env.now,
                is_emergency=True,
            )
            state.add_patient(patient)
            event_log.record(
                env.now,
                SimEventType.PATIENT_ARRIVED,
                patient.id,
                is_emergency=True,
                spike_number=spike_counter,
            )
            env.process(
                patient_journey(env, patient, state, resources, event_log, config, rng)
            )


# ── Staff shortage process ─────────────────────────────────────────────────────

def staff_shortage_process(
    env: simpy.Environment,
    state: HospitalStateManager,
    resources: HospitalResources,
    event_log: EventLog,
    config: SimulationConfig,
    rng: np.random.Generator,
) -> simpy.events.ProcessGenerator:
    """
    Randomly triggers temporary staff shortages (sick calls, shift gaps, etc.).
    Reduces SimPy resource capacity and restores it after the shortage ends.
    """
    while True:
        interval = rng.exponential(config.shortage_interval_mean)
        yield env.timeout(interval)

        duration = rng.exponential(config.shortage_duration_mean)
        fraction = config.shortage_staff_fraction

        doctors_affected = max(1, int(config.num_doctors * fraction))
        nurses_affected  = max(1, int(config.num_nurses  * fraction))

        # Update state manager and SimPy capacities
        state.trigger_staff_shortage(env.now, duration, fraction)
        resources.reduce_doctors(doctors_affected)
        resources.reduce_nurses(nurses_affected)

        event_log.record(
            env.now,
            SimEventType.STAFF_SHORTAGE,
            patient_id=None,
            duration_minutes=round(duration, 2),
            staff_fraction=fraction,
            doctors_affected=doctors_affected,
            nurses_affected=nurses_affected,
        )

        yield env.timeout(duration)

        # Restore capacity
        state.resolve_staff_shortage()
        resources.restore_doctors()
        resources.restore_nurses()

        event_log.record(
            env.now,
            SimEventType.STAFF_RESTORED,
            patient_id=None,
            duration_was=round(duration, 2),
        )

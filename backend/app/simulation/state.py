"""
HospitalStateManager – canonical, queryable view of simulation state.

All SimPy process functions write into this manager via its public API.
The manager is intentionally synchronous (SimPy runs synchronously).

Snapshot / rollback design
──────────────────────────
• snapshot() returns a frozen StateSnapshot dataclass – cheap, no copy of
  SimPy internals, only the derived metrics that the API needs.
• Full rollback (re-running from the event log) is handled by the engine;
  the state manager just needs to reset() and replay events.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum
from typing import Any

from app.simulation.config import SimulationConfig


# ── Domain enumerations ────────────────────────────────────────────────────────

class TriageLevel(str, Enum):
    CRITICAL = "critical"
    HIGH     = "high"
    MEDIUM   = "medium"
    LOW      = "low"


class PatientStatus(str, Enum):
    WAITING             = "waiting"
    IN_TRIAGE           = "in_triage"
    WAITING_FOR_DOCTOR  = "waiting_for_doctor"
    IN_TREATMENT        = "in_treatment"
    IN_ICU              = "in_icu"
    DISCHARGED          = "discharged"
    DECEASED            = "deceased"


# ── Patient entity ─────────────────────────────────────────────────────────────

@dataclass
class Patient:
    id: str
    arrival_time: float
    is_emergency: bool = False
    triage_level: TriageLevel | None = None
    status: PatientStatus = PatientStatus.WAITING

    # Timeline stamps (None until each milestone is reached)
    triage_complete_time: float | None = None
    doctor_assigned_time: float | None = None
    treatment_start_time: float | None = None
    icu_transfer_time: float | None = None
    discharge_time: float | None = None
    death_time: float | None = None

    assigned_doctor_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id":                   self.id,
            "arrival_time":         self.arrival_time,
            "is_emergency":         self.is_emergency,
            "triage_level":         self.triage_level.value if self.triage_level else None,
            "status":               self.status.value,
            "triage_complete_time": self.triage_complete_time,
            "doctor_assigned_time": self.doctor_assigned_time,
            "treatment_start_time": self.treatment_start_time,
            "icu_transfer_time":    self.icu_transfer_time,
            "discharge_time":       self.discharge_time,
            "death_time":           self.death_time,
            "assigned_doctor_id":   self.assigned_doctor_id,
        }

    @property
    def length_of_stay(self) -> float | None:
        """Minutes from arrival to outcome (if resolved)."""
        end = self.discharge_time or self.death_time
        if end is None:
            return None
        return end - self.arrival_time


# ── Snapshot dataclass (frozen, API-safe) ──────────────────────────────────────

@dataclass(frozen=True)
class StaffStatus:
    total_doctors:     int
    available_doctors: int
    total_nurses:      int
    available_nurses:  int
    shortage_active:   bool
    shortage_end_time: float | None


@dataclass(frozen=True)
class StateSnapshot:
    """
    Point-in-time frozen view of all tracked simulation metrics.
    Suitable for API serialisation and rollback anchoring.
    """
    snapshot_wall_time:    float   # Unix timestamp of when snapshot was taken
    simulation_time:       float   # Simulated clock (minutes)
    step_count:            int

    # Capacity
    total_icu_beds:        int
    icu_occupancy:         int
    available_icu_beds:    int
    total_regular_beds:    int
    regular_bed_occupancy: int
    available_regular_beds: int

    # Queue
    emergency_queue_length: int

    # Staff
    staff: StaffStatus
    doctor_workload:       float   # 0.0–1.0
    nurse_workload:        float

    # Equipment
    total_equipment:       int
    equipment_in_use:      int
    equipment_utilization: float

    # Throughput / outcomes
    total_arrivals:        int
    patient_throughput:    int     # = discharged_count
    discharged_count:      int
    deceased_count:        int

    # Active patients (list of dicts for JSON serialisation)
    active_patients:       list[dict[str, Any]]

    # Event log metadata
    event_history_count:   int

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_wall_time":    self.snapshot_wall_time,
            "simulation_time":       self.simulation_time,
            "step_count":            self.step_count,
            "icu": {
                "total_beds":   self.total_icu_beds,
                "occupancy":    self.icu_occupancy,
                "available":    self.available_icu_beds,
                "utilization":  round(self.icu_occupancy / max(1, self.total_icu_beds), 4),
            },
            "regular_ward": {
                "total_beds":   self.total_regular_beds,
                "occupancy":    self.regular_bed_occupancy,
                "available":    self.available_regular_beds,
                "utilization":  round(self.regular_bed_occupancy / max(1, self.total_regular_beds), 4),
            },
            "emergency_queue_length": self.emergency_queue_length,
            "staff": {
                "total_doctors":     self.staff.total_doctors,
                "available_doctors": self.staff.available_doctors,
                "total_nurses":      self.staff.total_nurses,
                "available_nurses":  self.staff.available_nurses,
                "shortage_active":   self.staff.shortage_active,
                "shortage_end_time": self.staff.shortage_end_time,
                "doctor_workload":   round(self.doctor_workload, 4),
                "nurse_workload":    round(self.nurse_workload, 4),
            },
            "equipment": {
                "total":       self.total_equipment,
                "in_use":      self.equipment_in_use,
                "utilization": round(self.equipment_utilization, 4),
            },
            "outcomes": {
                "total_arrivals":    self.total_arrivals,
                "patient_throughput": self.patient_throughput,
                "discharged":        self.discharged_count,
                "deceased":          self.deceased_count,
            },
            "active_patients":     self.active_patients,
            "event_history_count": self.event_history_count,
        }


# ── State manager ──────────────────────────────────────────────────────────────

class HospitalStateManager:
    """
    Mutable, incrementally-updated operational state of the simulated hospital.

    All mutation methods are called from within SimPy process functions and
    therefore execute synchronously on the SimPy event loop thread.
    """

    def __init__(self, config: SimulationConfig) -> None:
        self._config = config
        self._reset_counters()

    def _reset_counters(self) -> None:
        self.simulation_time: float = 0.0
        self.step_count: int = 0

        # Bed tracking
        self.total_icu_beds: int = self._config.icu_beds
        self.icu_occupancy: int = 0
        self.total_regular_beds: int = self._config.regular_beds
        self.regular_bed_occupancy: int = 0

        # Staff tracking
        self.total_doctors: int = self._config.num_doctors
        self.total_nurses: int = self._config.num_nurses
        self._doctors_unavailable: int = 0
        self._nurses_unavailable: int = 0
        self.staff_shortage_active: bool = False
        self.staff_shortage_end_time: float | None = None

        # Equipment
        self.total_equipment: int = self._config.num_equipment_units
        self.equipment_in_use: int = 0

        # Patient tracking
        self._active_patients: dict[str, Patient] = {}
        self.discharged_count: int = 0
        self.deceased_count: int = 0
        self.total_arrivals: int = 0
        self.emergency_queue_length: int = 0

        # Historical snapshots (for rollback anchoring)
        self._snapshots: list[StateSnapshot] = []

    # ── Snapshot history cap ───────────────────────────────────────────────────
    _SNAPSHOT_HISTORY_CAP: int = 500  # oldest evicted beyond this limit

    def reset(self) -> None:
        self._reset_counters()

    # ── Patient lifecycle mutations ────────────────────────────────────────────

    def add_patient(self, patient: Patient) -> None:
        self._active_patients[patient.id] = patient
        self.total_arrivals += 1
        self.emergency_queue_length += 1

    def move_to_triage(self, patient: Patient) -> None:
        patient.status = PatientStatus.IN_TRIAGE
        self.emergency_queue_length = max(0, self.emergency_queue_length - 1)

    def complete_triage(
        self,
        patient: Patient,
        triage_level: TriageLevel,
        sim_time: float,
    ) -> None:
        patient.triage_level = triage_level
        patient.triage_complete_time = sim_time
        patient.status = PatientStatus.WAITING_FOR_DOCTOR

    def assign_doctor(
        self,
        patient: Patient,
        doctor_id: str,
        sim_time: float,
    ) -> None:
        patient.assigned_doctor_id = doctor_id
        patient.doctor_assigned_time = sim_time

    def start_treatment(self, patient: Patient, sim_time: float) -> None:
        patient.treatment_start_time = sim_time
        patient.status = PatientStatus.IN_TREATMENT
        self.regular_bed_occupancy += 1
        self.equipment_in_use = min(self.total_equipment, self.equipment_in_use + 1)

    def transfer_to_icu(self, patient: Patient, sim_time: float) -> None:
        """Move patient from regular ward (or triage) to ICU."""
        if patient.status == PatientStatus.IN_TREATMENT:
            self.regular_bed_occupancy = max(0, self.regular_bed_occupancy - 1)
            self.equipment_in_use = max(0, self.equipment_in_use - 1)
        patient.icu_transfer_time = sim_time
        patient.status = PatientStatus.IN_ICU
        self.icu_occupancy += 1
        self.equipment_in_use = min(self.total_equipment, self.equipment_in_use + 1)

    def release_from_regular_ward(self, patient: Patient) -> None:
        """Release bed/equipment when transferring to ICU mid-treatment."""
        if patient.status == PatientStatus.IN_TREATMENT:
            self.regular_bed_occupancy = max(0, self.regular_bed_occupancy - 1)
            self.equipment_in_use = max(0, self.equipment_in_use - 1)
        patient.status = PatientStatus.WAITING_FOR_DOCTOR  # transitioning

    def discharge_patient(self, patient: Patient, sim_time: float) -> None:
        if patient.status == PatientStatus.IN_ICU:
            self.icu_occupancy = max(0, self.icu_occupancy - 1)
            self.equipment_in_use = max(0, self.equipment_in_use - 1)
        elif patient.status == PatientStatus.IN_TREATMENT:
            self.regular_bed_occupancy = max(0, self.regular_bed_occupancy - 1)
            self.equipment_in_use = max(0, self.equipment_in_use - 1)
        patient.discharge_time = sim_time
        patient.status = PatientStatus.DISCHARGED
        self._active_patients.pop(patient.id, None)
        self.discharged_count += 1

    def mark_deceased(self, patient: Patient, sim_time: float) -> None:
        if patient.status == PatientStatus.IN_ICU:
            self.icu_occupancy = max(0, self.icu_occupancy - 1)
            self.equipment_in_use = max(0, self.equipment_in_use - 1)
        elif patient.status == PatientStatus.IN_TREATMENT:
            self.regular_bed_occupancy = max(0, self.regular_bed_occupancy - 1)
            self.equipment_in_use = max(0, self.equipment_in_use - 1)
        patient.death_time = sim_time
        patient.status = PatientStatus.DECEASED
        self._active_patients.pop(patient.id, None)
        self.deceased_count += 1

    # ── Staff shortage mutations ───────────────────────────────────────────────

    def trigger_staff_shortage(
        self,
        sim_time: float,
        duration_minutes: float,
        fraction: float,
    ) -> None:
        self.staff_shortage_active = True
        self.staff_shortage_end_time = sim_time + duration_minutes
        self._doctors_unavailable = max(1, int(self.total_doctors * fraction))
        self._nurses_unavailable = max(1, int(self.total_nurses * fraction))

    def resolve_staff_shortage(self) -> None:
        self.staff_shortage_active = False
        self.staff_shortage_end_time = None
        self._doctors_unavailable = 0
        self._nurses_unavailable = 0

    # ── Computed properties ────────────────────────────────────────────────────

    @property
    def available_icu_beds(self) -> int:
        return max(0, self.total_icu_beds - self.icu_occupancy)

    @property
    def available_regular_beds(self) -> int:
        return max(0, self.total_regular_beds - self.regular_bed_occupancy)

    @property
    def available_doctors(self) -> int:
        return max(0, self.total_doctors - self._doctors_unavailable)

    @property
    def available_nurses(self) -> int:
        return max(0, self.total_nurses - self._nurses_unavailable)

    @property
    def doctor_workload(self) -> float:
        """Ratio of patients in treatment to available doctors (capped at 1.0)."""
        return min(1.0, self.regular_bed_occupancy / max(1, self.available_doctors))

    @property
    def nurse_workload(self) -> float:
        """Total bedded patients per available nurse (capped at 1.0)."""
        total_bedded = self.regular_bed_occupancy + self.icu_occupancy
        return min(1.0, total_bedded / max(1, self.available_nurses))

    @property
    def equipment_utilization(self) -> float:
        return self.equipment_in_use / max(1, self.total_equipment)

    @property
    def patient_throughput(self) -> int:
        return self.discharged_count

    @property
    def active_patients(self) -> list[Patient]:
        return list(self._active_patients.values())

    # ── Snapshot ───────────────────────────────────────────────────────────────

    def snapshot(self, event_history_count: int = 0) -> StateSnapshot:
        snap = StateSnapshot(
            snapshot_wall_time=time.time(),
            simulation_time=self.simulation_time,
            step_count=self.step_count,
            total_icu_beds=self.total_icu_beds,
            icu_occupancy=self.icu_occupancy,
            available_icu_beds=self.available_icu_beds,
            total_regular_beds=self.total_regular_beds,
            regular_bed_occupancy=self.regular_bed_occupancy,
            available_regular_beds=self.available_regular_beds,
            emergency_queue_length=self.emergency_queue_length,
            staff=StaffStatus(
                total_doctors=self.total_doctors,
                available_doctors=self.available_doctors,
                total_nurses=self.total_nurses,
                available_nurses=self.available_nurses,
                shortage_active=self.staff_shortage_active,
                shortage_end_time=self.staff_shortage_end_time,
            ),
            doctor_workload=self.doctor_workload,
            nurse_workload=self.nurse_workload,
            total_equipment=self.total_equipment,
            equipment_in_use=self.equipment_in_use,
            equipment_utilization=self.equipment_utilization,
            total_arrivals=self.total_arrivals,
            patient_throughput=self.patient_throughput,
            discharged_count=self.discharged_count,
            deceased_count=self.deceased_count,
            active_patients=[p.to_dict() for p in self.active_patients],
            event_history_count=event_history_count,
        )
        self._snapshots.append(snap)
        # Evict oldest snapshot if the history cap is exceeded
        if len(self._snapshots) > self._SNAPSHOT_HISTORY_CAP:
            self._snapshots = self._snapshots[-self._SNAPSHOT_HISTORY_CAP:]
        return snap

    def get_snapshots(self) -> list[StateSnapshot]:
        return list(self._snapshots)

    def clear_snapshots(self) -> None:
        self._snapshots.clear()

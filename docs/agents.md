# Multi-Agent Hospital Operations Layer

## Overview

Seven specialised agents observe simulation events, maintain internal state, and emit structured operational decisions with plain-English reasoning. The design is **explainable by construction**: every decision carries a reasoning string, confidence score, priority level, and tags.

Agents have no medical authority — they model operational roles: scheduling, routing, resource allocation, and escalation.

---

## Architecture

```
SimEvent stream
      │
      ▼
AgentRegistry.process_events(events, snapshot)
      │
      ├──► PatientAgent.on_event(event, snapshot)
      ├──► DoctorAgent.on_event(event, snapshot)
      ├──► NurseAgent.on_event(event, snapshot)
      ├──► AdminAgent.on_event(event, snapshot)
      ├──► ICUManagerAgent.on_event(event, snapshot)
      ├──► EmergencyCoordinatorAgent.on_event(event, snapshot)
      └──► ForecastingAgent.on_event(event, snapshot)
            │
            ▼
      list[DecisionLog] (returned + stored in agent._decision_log)
```

The registry collects all returned decisions and exposes them via the API.

---

## Decision Record Schema

Every decision is a `DecisionLog` with these fields:

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Unique decision identifier |
| `agent_id` | str | e.g. `"icu-manager-001"` |
| `agent_type` | str | e.g. `"icu_manager"` |
| `agent_name` | str | Human-readable name |
| `simulation_time` | float | Simulated time when decision was made |
| `wall_time` | float | Unix timestamp |
| `trigger_event_id` | UUID? | Event that triggered this decision |
| `trigger_event_type` | str? | e.g. `"patient_arrived"` |
| `decision` | str | What action/recommendation |
| `reasoning` | str | Plain-English justification |
| `priority` | enum | `info \| low \| medium \| high \| critical` |
| `confidence` | float | 0.0–1.0 |
| `tags` | list[str] | e.g. `["icu", "capacity", "critical"]` |
| `metadata` | dict | Agent-specific extra data |

---

## Agent Roster

### PatientAgent (`patient-agent-001`)
**Role**: Monitors patient population trends and flow anomalies.

| Trigger | Condition | Priority |
|---------|-----------|----------|
| Arrival surge | `arrivals > 2× 5-step moving average` | HIGH |
| High acuity ratio | `CRITICAL+HIGH > 30%` of active patients | HIGH |
| ICU spike | `ICU occupancy > 85%` | CRITICAL |
| Elevated mortality | `deaths/arrivals > 5%` | CRITICAL |

Internal state: arrival rate history, acuity distribution counters, step count.

---

### DoctorAgent (`doctor-agent-001`)
**Role**: Manages physician workload, prioritisation, and fatigue escalation.

| Trigger | Condition | Priority |
|---------|-----------|----------|
| Overload | `active_patients_per_doctor > 4` | HIGH |
| CRITICAL prioritisation | CRITICAL patient arrives | HIGH |
| Fatigue escalation | `workload > 90%` for 3+ consecutive steps | CRITICAL |
| Shortage response | Staff shortage event | HIGH |
| System critical | `doctor_workload > 95%` | CRITICAL |

---

### NurseAgent (`nurse-agent-001`)
**Role**: Monitors nursing capacity and coordinates queue support.

| Trigger | Condition | Priority |
|---------|-----------|----------|
| Workload critical | `nurse_workload > 90%` | CRITICAL |
| Queue support | `emergency_queue > 5` | HIGH |
| ICU nursing pressure | ICU transfer + `icu_occupancy > 80%` | HIGH |
| Shortage coverage | Staff shortage event | HIGH |

---

### AdminAgent (`admin-agent-001`)
**Role**: Hospital-level resource allocation and protocol management.

| Trigger | Condition | Priority |
|---------|-----------|----------|
| ICU reallocation | `icu_occupancy / total_icu > 80%` | HIGH |
| Ward overflow | `bed_occupancy > 90%` | CRITICAL |
| Emergency protocol | `emergency_queue > 10` | CRITICAL |
| Periodic audit | Every 5 simulation steps | INFO |
| Multi-system escalation | 2+ resources critical simultaneously | CRITICAL |

---

### ICUManagerAgent (`icu-manager-001`)
**Role**: Controls ICU admission decisions and step-down recommendations.

| Trigger | Condition | Priority |
|---------|-----------|----------|
| Admission approved | CRITICAL patient + ICU available | HIGH |
| Admission queued | CRITICAL patient + ICU full | HIGH |
| Capacity warning | `icu_occupancy > 80%` | MEDIUM |
| Critical alert | `icu_occupancy > 95%` | CRITICAL |
| Step-down recommendation | ICU patient improving (discharge event) | MEDIUM |

Internal state: admission queue, transfer history, capacity violation count.

---

### EmergencyCoordinatorAgent (`emergency-coord-001`)
**Role**: Classifies surge events and escalates alert level.

| Trigger | Condition | Decision |
|---------|-----------|----------|
| Minor spike | 1–2 extra patients | "ALERT_LEVEL_1" |
| Moderate spike | 3–5 extra patients | "ALERT_LEVEL_2" |
| Major spike | 6+ extra patients | "ALERT_LEVEL_3" |
| Double-trouble | Spike coincides with staff shortage | "DOUBLE_TROUBLE_ALERT" |
| All-clear | Queue normalises after spike | "ALL_CLEAR" |

Internal state: alert level, active spike flag, double-trouble detection.

---

### ForecastingAgent (`forecasting-agent-001`)
**Role**: Collects per-step time-series for statistical forecasting.

Records on every `simulation_stepped` event:

```json
{
  "step": 5,
  "sim_time": 300.0,
  "arrivals": 8,
  "icu_occupancy": 6,
  "ward_occupancy": 41,
  "emergency_queue": 2,
  "discharged": 5,
  "deaths": 0,
  "doctor_workload": 0.71,
  "nurse_workload": 0.58
}
```

Also emits demand trend decisions: `decreasing / stable / increasing / surge`.

---

## AgentRegistry

`AgentRegistry` (`backend/app/agents/registry.py`) manages the agent lifecycle:

```python
registry = get_registry()  # global singleton

# Dispatch events to all 7 agents
decisions = registry.process_events(new_raw_events, snapshot)

# Filtered global log
recent = registry.get_recent_decisions(
    limit=50,
    agent_id="icu-manager-001",
    priority="critical",
    since_sim_time=120.0,
)

# ForecastingAgent time-series (used by forecasting pipeline)
ts = registry.get_forecast_time_series()
```

All registry methods are protected by a separate `asyncio.Lock` (distinct from the engine lock), preventing concurrent write corruption under parallel API requests.

---

## Adding a New Agent

1. Create `backend/app/agents/my_agent.py`:

```python
from app.agents.base import AgentType, BaseAgent, DecisionLog
from app.simulation.events import SimEvent, SimEventType
from app.simulation.state import StateSnapshot

class MyAgent(BaseAgent):
    agent_type = AgentType.ADMIN  # choose the closest type

    def on_event(self, event: SimEvent, snapshot: StateSnapshot) -> list[DecisionLog]:
        if event.event_type == SimEventType.PATIENT_ARRIVED:
            return [self._decide(
                sim_time=event.simulation_time,
                decision="Custom action",
                reasoning="Because arrival rate exceeded threshold",
                priority=DecisionPriority.MEDIUM,
                confidence=0.85,
                trigger_event=event,
                tags=["custom"],
            )]
        return []

    def get_internal_state(self) -> dict:
        return {"custom_counter": self._counter}

    def get_reasoning_summary(self) -> str:
        return f"MyAgent: processed {self._events_processed} events"
```

2. Register it in `AgentRegistry.__init__()`:

```python
self._agents["my-agent-001"] = MyAgent("my-agent-001", "My Custom Agent")
```

No further wiring is needed — the registry dispatches all events to every registered agent automatically.

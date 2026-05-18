import type {
  HospitalSnapshot,
  AgentState,
  AgentDecision,
  ForecastBundle,
  OptimizationResult,
  TimeSeriesPoint,
  SimulationEvent,
  HealthResponse,
} from '@/types'

export const MOCK_SNAPSHOT: HospitalSnapshot = {
  simulation_time: 480,
  step_number: 8,
  icu_occupancy: 14,
  icu_total_beds: 20,
  icu_available_beds: 6,
  regular_bed_occupancy: 62,
  regular_total_beds: 80,
  regular_available_beds: 18,
  emergency_queue_length: 7,
  available_doctors: 11,
  total_doctors: 15,
  available_nurses: 34,
  total_nurses: 40,
  doctor_workload: 0.82,
  nurse_workload: 0.76,
  patient_throughput: 44,
  equipment_utilization: 0.63,
  active_patient_count: 76,
  discharged_count: 44,
  deceased_count: 2,
  status: 'ACTIVE',
}

export const MOCK_AGENTS: AgentState[] = [
  { agent_id: 'patient-agent-001', agent_type: 'patient', agent_name: 'Patient Flow Monitor', status: 'ACTIVE', events_processed: 94, decisions_made: 6, last_event_time: 478, reasoning_summary: 'Monitoring arrival surge patterns; current rate 2.1x baseline' },
  { agent_id: 'doctor-agent-001', agent_type: 'doctor', agent_name: 'Doctor Workload Manager', status: 'OVERLOADED', events_processed: 87, decisions_made: 9, last_event_time: 479, reasoning_summary: 'Doctor capacity at 82% — escalation protocol active' },
  { agent_id: 'nurse-agent-001', agent_type: 'nurse', agent_name: 'Nursing Coordinator', status: 'ACTIVE', events_processed: 91, decisions_made: 5, last_event_time: 476, reasoning_summary: 'Workload balanced; ICU nursing pressure moderate' },
  { agent_id: 'admin-agent-001', agent_type: 'admin', agent_name: 'Administrative Overseer', status: 'ALERT', events_processed: 88, decisions_made: 12, last_event_time: 475, reasoning_summary: 'ICU beds at 70% — reallocation protocol initiated' },
  { agent_id: 'icu-manager-001', agent_type: 'icu_manager', agent_name: 'ICU Manager', status: 'ALERT', events_processed: 76, decisions_made: 21, last_event_time: 479, reasoning_summary: '14/20 ICU beds occupied; 2 pending admission reviews' },
  { agent_id: 'emergency-coord-001', agent_type: 'emergency_coordinator', agent_name: 'Emergency Coordinator', status: 'ACTIVE', events_processed: 82, decisions_made: 8, last_event_time: 471, reasoning_summary: 'Minor spike detected 2h ago; all-clear not yet declared' },
  { agent_id: 'forecasting-agent-001', agent_type: 'forecasting', agent_name: 'Forecasting Agent', status: 'ACTIVE', events_processed: 72, decisions_made: 4, last_event_time: 480, reasoning_summary: 'Demand trend increasing; ICU saturation ETA ~6 steps' },
]

export const MOCK_DECISIONS: AgentDecision[] = [
  { id: 'd1', agent_id: 'icu-manager-001', agent_type: 'icu_manager', agent_name: 'ICU Manager', simulation_time: 479, wall_time: new Date().toISOString(), trigger_event_type: 'ICU_TRANSFER', decision: 'Approve ICU admission for patient P-0091', reasoning: 'Patient is CRITICAL severity; ICU capacity at 70% — admission approved per protocol', priority: 'HIGH', confidence: 0.95, tags: ['icu', 'admission', 'critical'] },
  { id: 'd2', agent_id: 'doctor-agent-001', agent_type: 'doctor', agent_name: 'Doctor Workload Manager', simulation_time: 477, wall_time: new Date().toISOString(), trigger_event_type: 'DOCTOR_ASSIGNED', decision: 'Escalate to fatigue management protocol', reasoning: 'Average doctor is managing 4.2 patients. Threshold exceeded. Recommend shift rotation.', priority: 'CRITICAL', confidence: 0.88, tags: ['workload', 'fatigue', 'escalation'] },
  { id: 'd3', agent_id: 'admin-agent-001', agent_type: 'admin', agent_name: 'Administrative Overseer', simulation_time: 475, wall_time: new Date().toISOString(), trigger_event_type: 'PATIENT_ARRIVED', decision: 'Initiate ICU bed reallocation plan', reasoning: 'ICU beds at 70%. Activating 4 reserve beds from elective surgery ward.', priority: 'HIGH', confidence: 0.91, tags: ['icu', 'capacity', 'reallocation'] },
  { id: 'd4', agent_id: 'emergency-coord-001', agent_type: 'emergency_coordinator', agent_name: 'Emergency Coordinator', simulation_time: 471, wall_time: new Date().toISOString(), trigger_event_type: 'EMERGENCY_SPIKE', decision: 'Classify as minor emergency spike', reasoning: '5 simultaneous arrivals detected. Queue depth 7. Activating minor spike protocol.', priority: 'MEDIUM', confidence: 0.84, tags: ['emergency', 'spike', 'protocol'] },
  { id: 'd5', agent_id: 'patient-agent-001', agent_type: 'patient', agent_name: 'Patient Flow Monitor', simulation_time: 468, wall_time: new Date().toISOString(), trigger_event_type: 'PATIENT_ARRIVED', decision: 'Alert: arrival rate 2.1x above baseline', reasoning: 'Observed 12 arrivals in last 60 min vs. 5.7 baseline. Flagging for surge preparation.', priority: 'MEDIUM', confidence: 0.79, tags: ['arrivals', 'surge', 'alert'] },
  { id: 'd6', agent_id: 'forecasting-agent-001', agent_type: 'forecasting', agent_name: 'Forecasting Agent', simulation_time: 480, wall_time: new Date().toISOString(), trigger_event_type: 'SIMULATION_STEPPED', decision: 'ICU saturation risk: HIGH within 6 steps', reasoning: 'Exponential smoothing projects ICU reaching 95% capacity in ~360 simulated minutes given current trend.', priority: 'HIGH', confidence: 0.82, tags: ['forecast', 'icu', 'saturation'] },
]

export const MOCK_TIME_SERIES: TimeSeriesPoint[] = [
  { step: 1, simulation_time: 60, arrivals: 6, icu_utilization: 0.25, ward_utilization: 0.30, queue_length: 2, discharged: 3, deceased: 0 },
  { step: 2, simulation_time: 120, arrivals: 8, icu_utilization: 0.35, ward_utilization: 0.42, queue_length: 3, discharged: 8, deceased: 0 },
  { step: 3, simulation_time: 180, arrivals: 7, icu_utilization: 0.45, ward_utilization: 0.52, queue_length: 4, discharged: 14, deceased: 1 },
  { step: 4, simulation_time: 240, arrivals: 11, icu_utilization: 0.55, ward_utilization: 0.60, queue_length: 6, discharged: 20, deceased: 1 },
  { step: 5, simulation_time: 300, arrivals: 9, icu_utilization: 0.60, ward_utilization: 0.65, queue_length: 5, discharged: 27, deceased: 1 },
  { step: 6, simulation_time: 360, arrivals: 13, icu_utilization: 0.65, ward_utilization: 0.71, queue_length: 8, discharged: 33, deceased: 2 },
  { step: 7, simulation_time: 420, arrivals: 10, icu_utilization: 0.68, ward_utilization: 0.74, queue_length: 6, discharged: 39, deceased: 2 },
  { step: 8, simulation_time: 480, arrivals: 12, icu_utilization: 0.70, ward_utilization: 0.78, queue_length: 7, discharged: 44, deceased: 2 },
]

export const MOCK_FORECAST: ForecastBundle = {
  demand: {
    forecaster_name: 'DemandForecaster',
    metric: 'patient_arrivals',
    horizon_steps: 6,
    points: [
      { step: 9, simulation_time: 540, value: 11.2, lower_bound: 8.5, upper_bound: 13.9 },
      { step: 10, simulation_time: 600, value: 12.1, lower_bound: 9.0, upper_bound: 15.2 },
      { step: 11, simulation_time: 660, value: 12.8, lower_bound: 9.4, upper_bound: 16.2 },
      { step: 12, simulation_time: 720, value: 13.5, lower_bound: 9.8, upper_bound: 17.2 },
      { step: 13, simulation_time: 780, value: 14.1, lower_bound: 10.2, upper_bound: 18.0 },
      { step: 14, simulation_time: 840, value: 14.8, lower_bound: 10.7, upper_bound: 18.9 },
    ],
    confidence: 0.78,
    trend_direction: 'increasing',
  },
  icu: {
    forecaster_name: 'ICUForecaster',
    metric: 'icu_utilization',
    horizon_steps: 6,
    points: [
      { step: 9, simulation_time: 540, value: 0.74, lower_bound: 0.68, upper_bound: 0.80 },
      { step: 10, simulation_time: 600, value: 0.79, lower_bound: 0.72, upper_bound: 0.86 },
      { step: 11, simulation_time: 660, value: 0.83, lower_bound: 0.75, upper_bound: 0.91 },
      { step: 12, simulation_time: 720, value: 0.87, lower_bound: 0.78, upper_bound: 0.96 },
      { step: 13, simulation_time: 780, value: 0.91, lower_bound: 0.81, upper_bound: 1.0 },
      { step: 14, simulation_time: 840, value: 0.95, lower_bound: 0.84, upper_bound: 1.0 },
    ],
    confidence: 0.82,
    trend_direction: 'surge',
    steps_to_saturation: 6,
    saturation_probability: 0.73,
  },
  ward: {
    forecaster_name: 'WardUtilizationForecaster',
    metric: 'ward_utilization',
    horizon_steps: 6,
    points: [
      { step: 9, simulation_time: 540, value: 0.81, lower_bound: 0.75, upper_bound: 0.87 },
      { step: 10, simulation_time: 600, value: 0.83, lower_bound: 0.76, upper_bound: 0.90 },
      { step: 11, simulation_time: 660, value: 0.85, lower_bound: 0.77, upper_bound: 0.93 },
      { step: 12, simulation_time: 720, value: 0.87, lower_bound: 0.78, upper_bound: 0.96 },
      { step: 13, simulation_time: 780, value: 0.89, lower_bound: 0.79, upper_bound: 0.99 },
      { step: 14, simulation_time: 840, value: 0.91, lower_bound: 0.80, upper_bound: 1.0 },
    ],
    confidence: 0.75,
    trend_direction: 'increasing',
  },
  staffing: {
    forecaster_name: 'StaffingForecaster',
    metric: 'staffing_requirement',
    horizon_steps: 6,
    points: [
      { step: 9, simulation_time: 540, value: 16, lower_bound: 14, upper_bound: 18 },
      { step: 10, simulation_time: 600, value: 17, lower_bound: 15, upper_bound: 19 },
      { step: 11, simulation_time: 660, value: 17, lower_bound: 15, upper_bound: 19 },
      { step: 12, simulation_time: 720, value: 18, lower_bound: 16, upper_bound: 20 },
      { step: 13, simulation_time: 780, value: 19, lower_bound: 16, upper_bound: 22 },
      { step: 14, simulation_time: 840, value: 20, lower_bound: 17, upper_bound: 23 },
    ],
    confidence: 0.70,
    trend_direction: 'increasing',
    peak_doctors: 20,
    peak_nurses: 48,
  },
  surge_risk: {
    risk_level: 'high',
    composite_score: 0.72,
    signals: {
      arrival_rate: 0.78,
      icu_pressure: 0.70,
      queue_depth: 0.65,
      demand_trend: 0.75,
    },
    recommended_actions: [
      'Activate surge staffing protocol — call in 4 additional doctors',
      'Convert 6 step-down beds to ICU capacity',
      'Initiate emergency queue triage bypass for CRITICAL patients',
      'Pre-position 10 additional equipment units in ICU wing',
    ],
    assessed_at: 480,
  },
  generated_at: new Date().toISOString(),
}

export const MOCK_OPTIMIZATION: OptimizationResult = {
  algorithm: 'genetic',
  best_score: 0.847,
  baseline_score: 0.693,
  improvement_pct: 22.2,
  best_solution: {
    doctors_on_duty: 18,
    nurses_on_duty: 44,
    icu_beds_active: 24,
    regular_beds_active: 85,
  },
  convergence_history: [0.693, 0.712, 0.741, 0.768, 0.789, 0.810, 0.826, 0.838, 0.843, 0.847],
  evaluations: 3600,
  wall_time_seconds: 0.018,
  recommendations: [
    'Increase doctors on duty from 11 to 18 (+64%) to reduce workload below critical threshold',
    'Add 10 nurses to bring ICU nursing ratio within safe bounds',
    'Activate 4 additional ICU beds from reserve capacity',
    'Open 5 additional ward beds to reduce overflow risk',
  ],
  generated_at: new Date().toISOString(),
}

export const MOCK_EVENTS: SimulationEvent[] = [
  { id: 'e1', simulation_time: 480, step_number: 8, event_type: 'PATIENT_ARRIVED', patient_id: 'P-0094', metadata: { triage: 'HIGH' } },
  { id: 'e2', simulation_time: 479, step_number: 8, event_type: 'ICU_TRANSFER', patient_id: 'P-0091', metadata: { from: 'emergency' } },
  { id: 'e3', simulation_time: 478, step_number: 8, event_type: 'TRIAGE_COMPLETE', patient_id: 'P-0093', metadata: { level: 'MEDIUM' } },
  { id: 'e4', simulation_time: 476, step_number: 8, event_type: 'DISCHARGE', patient_id: 'P-0078', metadata: { outcome: 'recovered' } },
  { id: 'e5', simulation_time: 474, step_number: 8, event_type: 'DOCTOR_ASSIGNED', patient_id: 'P-0092', metadata: { doctor_id: 'DR-003' } },
  { id: 'e6', simulation_time: 471, step_number: 8, event_type: 'EMERGENCY_SPIKE', metadata: { patients: 5 } },
  { id: 'e7', simulation_time: 468, step_number: 8, event_type: 'TREATMENT_STARTED', patient_id: 'P-0089', metadata: { ward: 'regular' } },
  { id: 'e8', simulation_time: 462, step_number: 8, event_type: 'PATIENT_ARRIVED', patient_id: 'P-0090', metadata: { triage: 'CRITICAL' } },
  { id: 'e9', simulation_time: 455, step_number: 7, event_type: 'STAFF_SHORTAGE', metadata: { affected_pct: 0.30 } },
  { id: 'e10', simulation_time: 445, step_number: 7, event_type: 'STAFF_RESTORED', metadata: {} },
]

export const MOCK_HEALTH: HealthResponse = {
  status: 'healthy',
  services: {
    postgres: { status: 'ok', latency_ms: 2.1 },
    redis: { status: 'ok', latency_ms: 0.8 },
  },
  uptime_seconds: 14400,
}

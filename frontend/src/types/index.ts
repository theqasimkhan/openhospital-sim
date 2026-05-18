// ─── Simulation Types ────────────────────────────────────────────────────────

export type SimulationStatus = 'IDLE' | 'ACTIVE' | 'COMPLETED'

export interface SimulationConfig {
  seed?: number
  icu_beds?: number
  regular_beds?: number
  num_doctors?: number
  num_nurses?: number
  num_equipment_units?: number
  mean_inter_arrival_minutes?: number
  simulation_duration_minutes?: number
}

export interface HospitalSnapshot {
  simulation_time: number
  step_number: number
  icu_occupancy: number
  icu_total_beds: number
  icu_available_beds: number
  regular_bed_occupancy: number
  regular_total_beds: number
  regular_available_beds: number
  emergency_queue_length: number
  available_doctors: number
  total_doctors: number
  available_nurses: number
  total_nurses: number
  doctor_workload: number
  nurse_workload: number
  patient_throughput: number
  equipment_utilization: number
  active_patient_count: number
  discharged_count: number
  deceased_count: number
  status: SimulationStatus
}

export interface SimulationEvent {
  id: string
  simulation_time: number
  step_number: number
  event_type: string
  patient_id?: string
  metadata?: Record<string, unknown>
}

export interface StepResult {
  step_number: number
  simulation_time: number
  events: SimulationEvent[]
  snapshot: HospitalSnapshot
  agent_decisions: AgentDecision[]
  events_count: number
}

// ─── Agent Types ─────────────────────────────────────────────────────────────

export type AgentStatus = 'IDLE' | 'ACTIVE' | 'OVERLOADED' | 'STANDBY' | 'ALERT'
export type AgentType = 'patient' | 'doctor' | 'nurse' | 'admin' | 'icu_manager' | 'emergency_coordinator' | 'forecasting'
export type DecisionPriority = 'INFO' | 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'

export interface AgentState {
  agent_id: string
  agent_type: AgentType
  agent_name: string
  status: AgentStatus
  events_processed: number
  decisions_made: number
  last_event_time?: number
  reasoning_summary?: string
}

export interface AgentDecision {
  id: string
  agent_id: string
  agent_type: AgentType
  agent_name: string
  simulation_time: number
  wall_time: string
  trigger_event_id?: string
  trigger_event_type?: string
  decision: string
  reasoning: string
  priority: DecisionPriority
  confidence: number
  tags: string[]
  metadata?: Record<string, unknown>
}

export interface AgentRegistry {
  total_agents: number
  total_events_processed: number
  total_decisions_made: number
  agents: AgentState[]
}

// ─── Forecasting Types ────────────────────────────────────────────────────────

export interface ForecastPoint {
  step: number
  simulation_time: number
  value: number
  lower_bound: number
  upper_bound: number
}

export interface ForecastResult {
  forecaster_name: string
  metric: string
  horizon_steps: number
  points: ForecastPoint[]
  confidence: number
  trend_direction: 'increasing' | 'decreasing' | 'stable' | 'surge'
  model_fit_score?: number
}

export interface SurgeRisk {
  risk_level: 'low' | 'medium' | 'high' | 'critical'
  composite_score: number
  signals: Record<string, number>
  recommended_actions: string[]
  assessed_at: number
}

export interface ForecastBundle {
  demand: ForecastResult
  icu: ForecastResult & { steps_to_saturation?: number; saturation_probability?: number }
  ward: ForecastResult
  staffing: ForecastResult & { peak_doctors?: number; peak_nurses?: number }
  surge_risk: SurgeRisk
  generated_at: string
}

export interface TimeSeriesPoint {
  step: number
  simulation_time: number
  arrivals: number
  icu_utilization: number
  ward_utilization: number
  queue_length: number
  discharged: number
  deceased: number
}

// ─── Optimization Types ───────────────────────────────────────────────────────

export interface OptimizationSolution {
  doctors_on_duty: number
  nurses_on_duty: number
  icu_beds_active: number
  regular_beds_active: number
}

export interface OptimizationResult {
  algorithm: 'greedy' | 'genetic' | 'pso'
  best_score: number
  baseline_score: number
  improvement_pct: number
  best_solution: OptimizationSolution
  convergence_history: number[]
  evaluations: number
  wall_time_seconds: number
  recommendations: string[]
  generated_at: string
}

// ─── API Response Wrappers ────────────────────────────────────────────────────

export interface ApiError {
  detail: string
  code?: string
}

export interface HealthResponse {
  status: 'healthy' | 'degraded' | 'unhealthy'
  services: {
    postgres: { status: string; latency_ms: number }
    redis: { status: string; latency_ms: number }
  }
  uptime_seconds: number
}

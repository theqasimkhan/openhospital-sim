import type {
  HospitalSnapshot,
  AgentState,
  AgentDecision,
  ForecastBundle,
  OptimizationResult,
  TimeSeriesPoint,
  SimulationEvent,
  StepResult,
  HealthResponse,
  SimulationConfig,
  AgentRegistry,
  SurgeRisk,
} from '@/types'
import {
  MOCK_SNAPSHOT,
  MOCK_AGENTS,
  MOCK_DECISIONS,
  MOCK_FORECAST,
  MOCK_OPTIMIZATION,
  MOCK_TIME_SERIES,
  MOCK_EVENTS,
  MOCK_HEALTH,
} from './mock-data'

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const url = `${BASE_URL}${path}`
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Unknown error' }))
    throw new Error(error.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

// ─── Health ───────────────────────────────────────────────────────────────────

export async function fetchHealth(): Promise<HealthResponse> {
  try {
    return await apiFetch<HealthResponse>('/api/v1/health')
  } catch {
    return MOCK_HEALTH
  }
}

// ─── Simulation ───────────────────────────────────────────────────────────────

export async function startSimulation(config?: SimulationConfig): Promise<HospitalSnapshot> {
  try {
    const body = config ? { config } : {}
    return await apiFetch<HospitalSnapshot>('/api/v1/simulation/start', {
      method: 'POST',
      body: JSON.stringify(body),
    })
  } catch {
    return MOCK_SNAPSHOT
  }
}

export async function stepSimulation(stepMinutes = 60): Promise<StepResult> {
  try {
    return await apiFetch<StepResult>('/api/v1/simulation/step', {
      method: 'POST',
      body: JSON.stringify({ step_minutes: stepMinutes }),
    })
  } catch {
    return {
      step_number: MOCK_SNAPSHOT.step_number,
      simulation_time: MOCK_SNAPSHOT.simulation_time,
      events: MOCK_EVENTS,
      snapshot: MOCK_SNAPSHOT,
      agent_decisions: MOCK_DECISIONS,
      events_count: MOCK_EVENTS.length,
    }
  }
}

export async function resetSimulation(): Promise<void> {
  try {
    await apiFetch('/api/v1/simulation/reset', { method: 'POST' })
  } catch {
    // ignore
  }
}

export async function fetchSimulationState(): Promise<HospitalSnapshot> {
  try {
    // Backend returns SimulationResponse: { status, simulation_time, engine_status, data: { state, resources } }
    const result = await apiFetch<{ data: { state: HospitalSnapshot } }>('/api/v1/simulation/state')
    return result?.data?.state ?? MOCK_SNAPSHOT
  } catch {
    return MOCK_SNAPSHOT
  }
}

export async function fetchSimulationEvents(params?: {
  since_time?: number
  since_step?: number
  event_type?: string
  limit?: number
}): Promise<SimulationEvent[]> {
  try {
    const qs = new URLSearchParams()
    if (params?.since_time != null) qs.set('since_time', String(params.since_time))
    if (params?.since_step != null) qs.set('since_step', String(params.since_step))
    if (params?.event_type) qs.set('event_type', params.event_type)
    if (params?.limit != null) qs.set('limit', String(params.limit))
    return await apiFetch<SimulationEvent[]>(`/api/v1/simulation/events?${qs}`)
  } catch {
    return MOCK_EVENTS
  }
}

// ─── Agents ───────────────────────────────────────────────────────────────────

export async function fetchAgents(): Promise<AgentState[]> {
  try {
    const result = await apiFetch<{ agents: AgentState[] } | AgentState[]>('/api/v1/agents')
    return Array.isArray(result) ? result : result.agents
  } catch {
    return MOCK_AGENTS
  }
}

export async function fetchAgentRegistry(): Promise<AgentRegistry> {
  try {
    return await apiFetch<AgentRegistry>('/api/v1/agents/registry')
  } catch {
    return {
      total_agents: MOCK_AGENTS.length,
      total_events_processed: MOCK_AGENTS.reduce((s, a) => s + a.events_processed, 0),
      total_decisions_made: MOCK_AGENTS.reduce((s, a) => s + a.decisions_made, 0),
      agents: MOCK_AGENTS,
    }
  }
}

export async function fetchRecentDecisions(params?: {
  agent_id?: string
  agent_type?: string
  priority?: string
  since_sim_time?: number
  limit?: number
}): Promise<AgentDecision[]> {
  try {
    const qs = new URLSearchParams()
    if (params?.agent_id) qs.set('agent_id', params.agent_id)
    if (params?.agent_type) qs.set('agent_type', params.agent_type)
    if (params?.priority) qs.set('priority', params.priority)
    if (params?.since_sim_time != null) qs.set('since_sim_time', String(params.since_sim_time))
    if (params?.limit != null) qs.set('limit', String(params.limit))
    return await apiFetch<AgentDecision[]>(`/api/v1/agents/decisions/recent?${qs}`)
  } catch {
    return MOCK_DECISIONS
  }
}

export async function fetchForecastTimeSeries(): Promise<TimeSeriesPoint[]> {
  try {
    const result = await apiFetch<{ time_series: TimeSeriesPoint[] } | TimeSeriesPoint[]>(
      '/api/v1/agents/forecast/timeseries'
    )
    const series = Array.isArray(result) ? result : result.time_series
    return Array.isArray(series) && series.length > 0 ? series : MOCK_TIME_SERIES
  } catch {
    return MOCK_TIME_SERIES
  }
}

export async function fetchAgentDetail(agentId: string): Promise<AgentState> {
  try {
    return await apiFetch<AgentState>(`/api/v1/agents/${agentId}`)
  } catch {
    return MOCK_AGENTS.find((a) => a.agent_id === agentId) ?? MOCK_AGENTS[0]
  }
}

export async function fetchAgentLogs(agentId: string, limit = 50): Promise<AgentDecision[]> {
  try {
    return await apiFetch<AgentDecision[]>(`/api/v1/agents/${agentId}/logs?limit=${limit}`)
  } catch {
    return MOCK_DECISIONS.filter((d) => d.agent_id === agentId)
  }
}

// ─── Forecasting ──────────────────────────────────────────────────────────────

export async function runForecasting(horizonSteps = 12): Promise<ForecastBundle> {
  try {
    return await apiFetch<ForecastBundle>('/api/v1/forecasting/run', {
      method: 'POST',
      body: JSON.stringify({ horizon_steps: horizonSteps }),
    })
  } catch {
    return MOCK_FORECAST
  }
}

export async function fetchLatestForecast(): Promise<ForecastBundle> {
  try {
    return await apiFetch<ForecastBundle>('/api/v1/forecasting/latest')
  } catch {
    return MOCK_FORECAST
  }
}

export async function fetchSurgeRisk(): Promise<SurgeRisk> {
  try {
    return await apiFetch<SurgeRisk>('/api/v1/forecasting/surge-risk')
  } catch {
    return MOCK_FORECAST.surge_risk
  }
}

// ─── Optimization ─────────────────────────────────────────────────────────────

export async function runOptimization(
  algorithm: 'greedy' | 'genetic' | 'pso' = 'genetic',
  maxIterations = 80
): Promise<OptimizationResult> {
  try {
    return await apiFetch<OptimizationResult>('/api/v1/optimization/run', {
      method: 'POST',
      body: JSON.stringify({ algorithm, max_iterations: maxIterations }),
    })
  } catch {
    return { ...MOCK_OPTIMIZATION, algorithm }
  }
}

export async function fetchLatestOptimization(): Promise<OptimizationResult> {
  try {
    return await apiFetch<OptimizationResult>('/api/v1/optimization/results')
  } catch {
    return MOCK_OPTIMIZATION
  }
}

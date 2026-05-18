'use client'

import { useEffect, useState, useCallback } from 'react'
import { AppShell } from '@/components/layout/AppShell'
import { SimulationControls } from '@/components/simulation/SimulationControls'
import { EventTimeline } from '@/components/simulation/EventTimeline'
import { HospitalOverviewCards } from '@/components/dashboard/HospitalOverviewCards'
import { Panel, SectionHeader } from '@/components/shared/MetricCard'
import {
  fetchSimulationState,
  fetchSimulationEvents,
  startSimulation,
  stepSimulation,
  resetSimulation,
} from '@/lib/api'
import { MOCK_SNAPSHOT, MOCK_EVENTS } from '@/lib/mock-data'
import type { HospitalSnapshot, SimulationEvent, AgentDecision, SimulationConfig } from '@/types'
import { PriorityBadge } from '@/components/shared/StatusBadge'

export default function SimulationPage() {
  const [snapshot, setSnapshot] = useState<HospitalSnapshot>(MOCK_SNAPSHOT)
  const [events, setEvents] = useState<SimulationEvent[]>(MOCK_EVENTS)
  const [decisions, setDecisions] = useState<AgentDecision[]>([])
  const [loading, setLoading] = useState(false)
  const [log, setLog] = useState<string[]>(['[SIM] Dashboard loaded — mock data active'])

  const appendLog = (msg: string) => {
    setLog((prev) => [`[${new Date().toLocaleTimeString()}] ${msg}`, ...prev.slice(0, 49)])
  }

  const handleStart = useCallback(async (config?: SimulationConfig) => {
    setLoading(true)
    try {
      const snap = await startSimulation(config)
      setSnapshot(snap)
      setEvents([])
      setDecisions([])
      appendLog(`Simulation started — seed=${config?.seed ?? 42}, ICU beds=${config?.icu_beds ?? 20}`)
    } catch (e) {
      appendLog(`ERROR: ${e}`)
    } finally {
      setLoading(false)
    }
  }, [])

  const handleStep = useCallback(async (minutes: number) => {
    setLoading(true)
    try {
      const result = await stepSimulation(minutes)
      setSnapshot(result.snapshot)
      setEvents((prev) => [...result.events, ...prev].slice(0, 200))
      setDecisions((prev) => [...result.agent_decisions, ...prev].slice(0, 50))
      appendLog(
        `Step ${result.step_number} complete — T=${result.simulation_time}m, ${result.events_count} events, ${result.agent_decisions.length} decisions`
      )
    } catch (e) {
      appendLog(`ERROR: ${e}`)
    } finally {
      setLoading(false)
    }
  }, [])

  const handleReset = useCallback(async () => {
    setLoading(true)
    try {
      await resetSimulation()
      const snap = await fetchSimulationState()
      setSnapshot(snap)
      setEvents([])
      setDecisions([])
      appendLog('Simulation reset to IDLE')
    } catch (e) {
      appendLog(`ERROR: ${e}`)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    Promise.all([fetchSimulationState(), fetchSimulationEvents({ limit: 100 })]).then(
      ([snap, evts]) => {
        setSnapshot(snap)
        setEvents(evts)
      }
    )
  }, [])

  return (
    <AppShell title="Simulation Engine" subtitle="Discrete-event hospital model · SimPy backend">
      <div className="space-y-5 max-w-[1600px]">
        {/* Top: controls + state */}
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-5">
          <div className="xl:col-span-2">
            <SimulationControls
              snapshot={snapshot}
              onStart={handleStart}
              onStep={handleStep}
              onReset={handleReset}
              loading={loading}
            />
          </div>

          {/* Ops log */}
          <Panel noPad className="flex flex-col">
            <div className="p-3 border-b border-surface-border flex-shrink-0">
              <SectionHeader title="Operations Log" subtitle="Real-time action feed" />
            </div>
            <div className="flex-1 overflow-y-auto p-3 space-y-1.5 max-h-[220px]">
              {log.map((entry, i) => (
                <div key={i} className="text-[11px] font-mono text-text-muted leading-relaxed">
                  {entry}
                </div>
              ))}
            </div>
          </Panel>
        </div>

        {/* Hospital state */}
        <HospitalOverviewCards snapshot={snapshot} />

        {/* Timeline + decisions */}
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
          <div className="min-h-[420px]">
            <EventTimeline events={events} />
          </div>

          {/* Agent decisions from last step */}
          <Panel noPad className="flex flex-col min-h-[420px]">
            <div className="p-4 border-b border-surface-border flex-shrink-0">
              <SectionHeader
                title="Agent Decisions"
                subtitle={`${decisions.length} decisions from recent steps`}
              />
            </div>
            <div className="flex-1 overflow-y-auto p-4 space-y-2">
              {decisions.length === 0 && (
                <div className="text-center text-text-muted text-sm py-8">
                  Run a simulation step to see agent decisions
                </div>
              )}
              {decisions.map((d) => (
                <div
                  key={d.id}
                  className="p-3 bg-surface-3 border border-surface-border rounded-lg space-y-1.5"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs font-semibold text-text-primary truncate">{d.agent_name}</span>
                    <PriorityBadge priority={d.priority} />
                  </div>
                  <p className="text-xs text-text-secondary">{d.decision}</p>
                  <p className="text-[10px] text-text-muted leading-relaxed">{d.reasoning}</p>
                  <div className="flex items-center gap-2 text-[10px] font-mono text-text-muted">
                    <span>T={d.simulation_time}m</span>
                    <span>·</span>
                    <span>conf={d.confidence.toFixed(2)}</span>
                  </div>
                </div>
              ))}
            </div>
          </Panel>
        </div>
      </div>
    </AppShell>
  )
}

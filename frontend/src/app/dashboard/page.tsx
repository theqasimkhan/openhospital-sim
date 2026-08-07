'use client'

import { useEffect, useState, useCallback } from 'react'
import { RefreshCw } from 'lucide-react'
import { AppShell } from '@/components/layout/AppShell'
import { HospitalOverviewCards } from '@/components/dashboard/HospitalOverviewCards'
import { ICUOccupancyChart } from '@/components/dashboard/ICUOccupancyChart'
import { EmergencyQueuePanel } from '@/components/dashboard/EmergencyQueuePanel'
import { PatientFlowGraph } from '@/components/dashboard/PatientFlowGraph'
import { StaffUtilizationChart } from '@/components/dashboard/StaffUtilizationChart'
import { AgentDecisionLogs } from '@/components/agents/AgentDecisionLogs'
import { fetchSimulationState, fetchForecastTimeSeries, fetchRecentDecisions } from '@/lib/api'
import { MOCK_SNAPSHOT, MOCK_TIME_SERIES, MOCK_DECISIONS } from '@/lib/mock-data'
import type { HospitalSnapshot, TimeSeriesPoint, AgentDecision } from '@/types'

export default function DashboardPage() {
  const [snapshot, setSnapshot] = useState<HospitalSnapshot>(MOCK_SNAPSHOT)
  const [timeSeries, setTimeSeries] = useState<TimeSeriesPoint[]>(MOCK_TIME_SERIES)
  const [decisions, setDecisions] = useState<AgentDecision[]>(MOCK_DECISIONS)
  const [loading, setLoading] = useState(false)
  const [lastRefresh, setLastRefresh] = useState(new Date())

  const refresh = useCallback(async () => {
    setLoading(true)
    try {
      const [snap, ts, dec] = await Promise.all([
        fetchSimulationState(),
        fetchForecastTimeSeries(),
        fetchRecentDecisions({ limit: 8 }),
      ])
      if (snap) setSnapshot(snap)
      if (Array.isArray(ts) && ts.length > 0) setTimeSeries(ts)
      if (Array.isArray(dec)) setDecisions(dec)
      setLastRefresh(new Date())
    } catch {
      // individual fetches already handle errors with mock fallbacks
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    refresh()
    const interval = setInterval(refresh, 30000)
    return () => clearInterval(interval)
  }, [refresh])

  const actions = (
    <button
      onClick={refresh}
      disabled={loading}
      className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-surface-3 border border-surface-border text-xs font-medium text-text-secondary hover:text-text-primary hover:border-brand-cyan/40 transition-all"
    >
      <RefreshCw className={`w-3 h-3 ${loading ? 'animate-spin' : ''}`} />
      Refresh
    </button>
  )

  return (
    <AppShell
      title="Hospital Command Center"
      subtitle={`Live — last refresh ${lastRefresh.toLocaleTimeString()}`}
      actions={actions}
    >
      <div className="space-y-5 max-w-[1600px]">
        {/* Overview KPIs + capacity */}
        <HospitalOverviewCards snapshot={snapshot} />

        {/* Mid row: ICU chart + Emergency queue */}
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
          <ICUOccupancyChart timeSeries={timeSeries} icuTotal={snapshot.icu_total_beds} />
          <EmergencyQueuePanel
            timeSeries={timeSeries}
            currentQueue={snapshot.emergency_queue_length}
            emergencyQueueLength={snapshot.emergency_queue_length}
          />
        </div>

        {/* Bottom row: Patient flow + Staff radar + Recent agent decisions */}
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-5">
          <div className="xl:col-span-2 space-y-5">
            <PatientFlowGraph timeSeries={timeSeries} />
          </div>
          <StaffUtilizationChart snapshot={snapshot} />
        </div>

        {/* Agent decisions strip */}
        <AgentDecisionLogs decisions={decisions} compact />
      </div>
    </AppShell>
  )
}

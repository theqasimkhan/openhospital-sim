'use client'

import { useEffect, useState, useCallback } from 'react'
import { Brain, RefreshCw, Activity, AlertCircle } from 'lucide-react'
import { AppShell } from '@/components/layout/AppShell'
import { AgentDecisionLogs } from '@/components/agents/AgentDecisionLogs'
import { Panel, SectionHeader, MetricCard } from '@/components/shared/MetricCard'
import { AgentStatusBadge } from '@/components/shared/StatusBadge'
import { fetchAgents, fetchRecentDecisions, fetchAgentRegistry } from '@/lib/api'
import { MOCK_AGENTS, MOCK_DECISIONS } from '@/lib/mock-data'
import type { AgentState, AgentDecision, AgentRegistry } from '@/types'
import clsx from 'clsx'

const AGENT_TYPE_ICONS: Record<string, string> = {
  patient: '🏥',
  doctor: '🩺',
  nurse: '💉',
  admin: '📋',
  icu_manager: '🚨',
  emergency_coordinator: '⚡',
  forecasting: '📈',
}

export default function AgentsPage() {
  const [agents, setAgents] = useState<AgentState[]>(MOCK_AGENTS)
  const [decisions, setDecisions] = useState<AgentDecision[]>(MOCK_DECISIONS)
  const [registry, setRegistry] = useState<AgentRegistry | null>(null)
  const [selected, setSelected] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const refresh = useCallback(async () => {
    setLoading(true)
    const [ags, decs, reg] = await Promise.all([
      fetchAgents(),
      fetchRecentDecisions({ limit: 100 }),
      fetchAgentRegistry(),
    ])
    setAgents(ags)
    setDecisions(decs)
    setRegistry(reg)
    setLoading(false)
  }, [])

  useEffect(() => { refresh() }, [refresh])

  const filteredDecisions = selected
    ? decisions.filter((d) => d.agent_id === selected)
    : decisions

  const selectedAgent = agents.find((a) => a.agent_id === selected)

  return (
    <AppShell
      title="Agent Operations"
      subtitle="7 AI agents · Multi-agent hospital operations layer"
      actions={
        <button
          onClick={refresh}
          disabled={loading}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-surface-3 border border-surface-border text-xs font-medium text-text-secondary hover:text-text-primary transition-all"
        >
          <RefreshCw className={`w-3 h-3 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      }
    >
      <div className="space-y-5 max-w-[1600px]">
        {/* Registry summary */}
        {registry && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <MetricCard label="Total Agents" value={registry.total_agents} icon={<Brain className="w-4 h-4" />} />
            <MetricCard label="Events Processed" value={registry.total_events_processed} icon={<Activity className="w-4 h-4" />} />
            <MetricCard label="Decisions Made" value={registry.total_decisions_made} icon={<AlertCircle className="w-4 h-4" />} />
            <MetricCard
              label="Alert Agents"
              value={agents.filter((a) => a.status === 'ALERT' || a.status === 'OVERLOADED').length}
              variant={agents.some((a) => a.status === 'OVERLOADED') ? 'critical' : agents.some((a) => a.status === 'ALERT') ? 'warn' : 'ok'}
            />
          </div>
        )}

        {/* Agent roster */}
        <Panel>
          <SectionHeader title="Agent Roster" subtitle="Click an agent to filter decision logs" className="mb-4" />
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4 gap-3">
            {agents.map((agent) => (
              <button
                key={agent.agent_id}
                onClick={() => setSelected(selected === agent.agent_id ? null : agent.agent_id)}
                className={clsx(
                  'text-left p-3 rounded-lg border transition-all space-y-2',
                  selected === agent.agent_id
                    ? 'bg-brand-cyan/5 border-brand-cyan/30'
                    : 'bg-surface-3 border-surface-border hover:border-surface-4'
                )}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <span className="text-lg leading-none">{AGENT_TYPE_ICONS[agent.agent_type] ?? '🤖'}</span>
                    <div>
                      <div className="text-xs font-semibold text-text-primary">{agent.agent_name}</div>
                      <div className="text-[10px] font-mono text-text-muted">{agent.agent_id}</div>
                    </div>
                  </div>
                  <AgentStatusBadge status={agent.status} />
                </div>
                <p className="text-[11px] text-text-muted leading-relaxed line-clamp-2">
                  {agent.reasoning_summary ?? 'No recent activity'}
                </p>
                <div className="flex items-center justify-between text-[10px] font-mono text-text-muted pt-1 border-t border-surface-border">
                  <span>{agent.events_processed} events</span>
                  <span>{agent.decisions_made} decisions</span>
                  {agent.last_event_time != null && <span>T={agent.last_event_time}m</span>}
                </div>
              </button>
            ))}
          </div>
        </Panel>

        {/* Detail pane (if selected) */}
        {selectedAgent && (
          <Panel className="border-brand-cyan/20">
            <SectionHeader
              title={selectedAgent.agent_name}
              subtitle={`${selectedAgent.agent_type} · ${selectedAgent.agent_id}`}
              className="mb-3"
              actions={<AgentStatusBadge status={selectedAgent.status} />}
            />
            <p className="text-sm text-text-secondary">{selectedAgent.reasoning_summary}</p>
          </Panel>
        )}

        {/* Decision log */}
        <AgentDecisionLogs decisions={filteredDecisions} />
      </div>
    </AppShell>
  )
}

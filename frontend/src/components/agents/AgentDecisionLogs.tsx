'use client'

import { useState } from 'react'
import clsx from 'clsx'
import { ChevronDown, ChevronUp, Brain, Tag } from 'lucide-react'
import { Panel, SectionHeader } from '@/components/shared/MetricCard'
import { PriorityBadge } from '@/components/shared/StatusBadge'
import type { AgentDecision, DecisionPriority } from '@/types'

interface Props {
  decisions: AgentDecision[]
  compact?: boolean
}

const AGENT_TYPE_COLORS: Record<string, string> = {
  patient:                'text-brand-cyan',
  doctor:                 'text-status-ok',
  nurse:                  'text-brand-blue',
  admin:                  'text-brand-purple',
  icu_manager:            'text-status-warn',
  emergency_coordinator:  'text-status-critical',
  forecasting:            'text-text-secondary',
}

const PRIORITY_ORDER: DecisionPriority[] = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO']

export function AgentDecisionLogs({ decisions, compact }: Props) {
  const [expanded, setExpanded] = useState<string | null>(null)
  const [filterPriority, setFilterPriority] = useState<string>('ALL')
  const [filterAgent, setFilterAgent] = useState<string>('ALL')

  const agentIds = Array.from(new Set(decisions.map((d) => d.agent_id)))

  const filtered = decisions
    .filter((d) => filterPriority === 'ALL' || d.priority === filterPriority)
    .filter((d) => filterAgent === 'ALL' || d.agent_id === filterAgent)
    .sort((a, b) => {
      const pi = PRIORITY_ORDER.indexOf(a.priority)
      const pj = PRIORITY_ORDER.indexOf(b.priority)
      if (pi !== pj) return pi - pj
      return b.simulation_time - a.simulation_time
    })

  if (compact) {
    return (
      <Panel noPad>
        <div className="p-4 border-b border-surface-border">
          <SectionHeader
            title="Recent Agent Decisions"
            subtitle={`${decisions.length} decisions across all agents`}
          />
        </div>
        <div className="divide-y divide-surface-border">
          {filtered.slice(0, 6).map((d) => (
            <div key={d.id} className="flex items-start gap-3 px-4 py-3">
              <Brain className={clsx('w-4 h-4 mt-0.5 flex-shrink-0', AGENT_TYPE_COLORS[d.agent_type])} />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className={clsx('text-[10px] font-bold uppercase tracking-wider', AGENT_TYPE_COLORS[d.agent_type])}>
                    {d.agent_name}
                  </span>
                  <PriorityBadge priority={d.priority} />
                  <span className="text-[10px] font-mono text-text-muted">T={d.simulation_time}m</span>
                </div>
                <p className="text-xs text-text-secondary mt-0.5 truncate">{d.decision}</p>
              </div>
            </div>
          ))}
          {decisions.length === 0 && (
            <div className="px-4 py-6 text-center text-xs text-text-muted">No decisions yet</div>
          )}
        </div>
      </Panel>
    )
  }

  return (
    <Panel noPad className="flex flex-col">
      {/* Header + filters */}
      <div className="p-4 border-b border-surface-border space-y-3">
        <SectionHeader
          title="Agent Decision Log"
          subtitle={`${filtered.length} decisions filtered · ${decisions.length} total`}
        />
        <div className="flex flex-wrap gap-2">
          <select
            value={filterPriority}
            onChange={(e) => setFilterPriority(e.target.value)}
            className="bg-surface-3 border border-surface-border text-xs text-text-secondary rounded-md px-2 py-1.5 focus:outline-none focus:border-brand-cyan/50"
          >
            <option value="ALL">All Priorities</option>
            {PRIORITY_ORDER.map((p) => <option key={p} value={p}>{p}</option>)}
          </select>
          <select
            value={filterAgent}
            onChange={(e) => setFilterAgent(e.target.value)}
            className="bg-surface-3 border border-surface-border text-xs text-text-secondary rounded-md px-2 py-1.5 focus:outline-none focus:border-brand-cyan/50"
          >
            <option value="ALL">All Agents</option>
            {agentIds.map((id) => <option key={id} value={id}>{id}</option>)}
          </select>
        </div>
      </div>

      {/* Decision list */}
      <div className="divide-y divide-surface-border overflow-y-auto max-h-[600px]">
        {filtered.length === 0 && (
          <div className="text-center text-text-muted text-sm py-12">No decisions match filters</div>
        )}
        {filtered.map((d) => {
          const isOpen = expanded === d.id
          return (
            <div key={d.id} className="hover:bg-surface-3/50 transition-colors">
              <button
                className="w-full flex items-start gap-3 px-4 py-3 text-left"
                onClick={() => setExpanded(isOpen ? null : d.id)}
              >
                <Brain className={clsx('w-4 h-4 mt-0.5 flex-shrink-0', AGENT_TYPE_COLORS[d.agent_type])} />
                <div className="flex-1 min-w-0 space-y-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className={clsx('text-[10px] font-bold uppercase tracking-wider', AGENT_TYPE_COLORS[d.agent_type])}>
                      {d.agent_name}
                    </span>
                    <PriorityBadge priority={d.priority} />
                    <span className="text-[10px] font-mono text-text-muted">T={d.simulation_time}m</span>
                    <span className="text-[10px] font-mono text-text-muted">conf={d.confidence.toFixed(2)}</span>
                  </div>
                  <p className="text-xs font-medium text-text-primary">{d.decision}</p>
                  {!isOpen && (
                    <p className="text-[11px] text-text-muted truncate">{d.reasoning}</p>
                  )}
                </div>
                {isOpen ? (
                  <ChevronUp className="w-4 h-4 text-text-muted flex-shrink-0" />
                ) : (
                  <ChevronDown className="w-4 h-4 text-text-muted flex-shrink-0" />
                )}
              </button>

              {isOpen && (
                <div className="px-4 pb-4 pl-11 space-y-3 animate-slide-in">
                  <div className="p-3 bg-surface-3 rounded-lg border border-surface-border">
                    <div className="text-[10px] font-semibold tracking-widest uppercase text-text-muted mb-1.5">
                      Reasoning
                    </div>
                    <p className="text-xs text-text-secondary leading-relaxed">{d.reasoning}</p>
                  </div>
                  {d.tags?.length > 0 && (
                    <div className="flex items-center gap-1.5 flex-wrap">
                      <Tag className="w-3 h-3 text-text-muted" />
                      {d.tags.map((tag) => (
                        <span
                          key={tag}
                          className="inline-flex items-center px-2 py-0.5 rounded text-[10px] bg-surface-4 text-text-muted border border-surface-border font-mono"
                        >
                          {tag}
                        </span>
                      ))}
                    </div>
                  )}
                  {d.trigger_event_type && (
                    <div className="text-[10px] font-mono text-text-muted">
                      Triggered by: {d.trigger_event_type}
                    </div>
                  )}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </Panel>
  )
}

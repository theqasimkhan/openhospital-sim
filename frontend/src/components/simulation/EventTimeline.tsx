'use client'

import { useState } from 'react'
import {
  UserPlus, Activity, Stethoscope, ArrowUpCircle, LogOut, Skull,
  AlertTriangle, UserX, UserCheck, Zap, Filter,
} from 'lucide-react'
import clsx from 'clsx'
import { Panel, SectionHeader } from '@/components/shared/MetricCard'
import type { SimulationEvent } from '@/types'

interface Props {
  events: SimulationEvent[]
}

const EVENT_CONFIG: Record<string, { icon: React.ElementType; color: string; label: string }> = {
  PATIENT_ARRIVED:      { icon: UserPlus,     color: 'text-brand-cyan border-brand-cyan/30 bg-brand-cyan/5',       label: 'Arrived' },
  TRIAGE_COMPLETE:      { icon: Activity,     color: 'text-brand-blue border-brand-blue/30 bg-brand-blue/5',       label: 'Triaged' },
  DOCTOR_ASSIGNED:      { icon: Stethoscope,  color: 'text-status-ok border-status-ok/30 bg-status-ok/5',         label: 'Dr. Assigned' },
  TREATMENT_STARTED:    { icon: Zap,          color: 'text-status-ok border-status-ok/30 bg-status-ok/5',         label: 'Treatment' },
  ICU_TRANSFER:         { icon: ArrowUpCircle,color: 'text-status-warn border-status-warn/30 bg-status-warn/5',   label: 'ICU Transfer' },
  DISCHARGE:            { icon: LogOut,       color: 'text-status-ok border-status-ok/30 bg-status-ok/5',         label: 'Discharged' },
  PATIENT_DEATH:        { icon: Skull,        color: 'text-status-critical border-status-critical/30 bg-status-critical/5', label: 'Death' },
  EMERGENCY_SPIKE:      { icon: AlertTriangle,color: 'text-status-critical border-status-critical/30 bg-status-critical/5', label: 'Emrg. Spike' },
  STAFF_SHORTAGE:       { icon: UserX,        color: 'text-status-warn border-status-warn/30 bg-status-warn/5',   label: 'Staff Shortage' },
  STAFF_RESTORED:       { icon: UserCheck,    color: 'text-status-ok border-status-ok/30 bg-status-ok/5',         label: 'Staff Restored' },
  SIMULATION_STARTED:   { icon: Activity,     color: 'text-brand-cyan border-brand-cyan/30 bg-brand-cyan/5',       label: 'Sim Started' },
  SIMULATION_STEPPED:   { icon: Activity,     color: 'text-text-muted border-surface-border bg-surface-3',         label: 'Step' },
  SIMULATION_RESET:     { icon: Activity,     color: 'text-text-muted border-surface-border bg-surface-3',         label: 'Reset' },
}

const ALL_EVENT_TYPES = Object.keys(EVENT_CONFIG)

export function EventTimeline({ events }: Props) {
  const [filter, setFilter] = useState<string>('ALL')
  const [limit, setLimit] = useState(20)

  const filtered = (filter === 'ALL' ? events : events.filter((e) => e.event_type === filter))
    .slice(0, limit)

  return (
    <Panel noPad className="flex flex-col h-full">
      <div className="p-4 border-b border-surface-border flex-shrink-0">
        <SectionHeader
          title="Event Timeline"
          subtitle={`${events.length} total events · ${filtered.length} shown`}
          actions={
            <div className="flex items-center gap-2">
              <Filter className="w-3.5 h-3.5 text-text-muted" />
              <select
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
                className="bg-surface-3 border border-surface-border text-xs text-text-secondary rounded-md px-2 py-1 focus:outline-none focus:border-brand-cyan/50"
              >
                <option value="ALL">All Events</option>
                {ALL_EVENT_TYPES.map((t) => (
                  <option key={t} value={t}>{t.replace(/_/g, ' ')}</option>
                ))}
              </select>
            </div>
          }
        />
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-2">
        {filtered.length === 0 && (
          <div className="text-center text-text-muted text-sm py-8">No events to display</div>
        )}
        {filtered.map((event) => {
          const cfg = EVENT_CONFIG[event.event_type] ?? EVENT_CONFIG.SIMULATION_STEPPED
          const Icon = cfg.icon
          return (
            <div
              key={event.id}
              className={clsx(
                'flex items-start gap-3 p-2.5 rounded-lg border transition-all',
                cfg.color
              )}
            >
              <div className="w-5 h-5 flex items-center justify-center flex-shrink-0 mt-0.5">
                <Icon className="w-3.5 h-3.5" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs font-semibold">{cfg.label}</span>
                  <span className="text-[10px] font-mono text-text-muted flex-shrink-0">
                    T={event.simulation_time}m
                  </span>
                </div>
                <div className="text-[10px] text-current opacity-70 truncate mt-0.5">
                  {event.patient_id ? `Patient: ${event.patient_id}` : event.event_type.replace(/_/g, ' ')}
                  {event.metadata && Object.keys(event.metadata).length > 0 && (
                    <span className="ml-2 font-mono">
                      {JSON.stringify(event.metadata).slice(0, 60)}
                    </span>
                  )}
                </div>
              </div>
              <div className="text-[10px] font-mono text-text-muted flex-shrink-0">
                S{event.step_number}
              </div>
            </div>
          )
        })}
        {events.length > limit && (
          <button
            onClick={() => setLimit((l) => l + 20)}
            className="w-full py-2 text-xs text-text-muted hover:text-text-secondary border border-dashed border-surface-border rounded-lg transition-colors"
          >
            Load more ({events.length - limit} remaining)
          </button>
        )}
      </div>
    </Panel>
  )
}

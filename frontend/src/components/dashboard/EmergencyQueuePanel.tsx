'use client'

import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import { AlertTriangle, Clock } from 'lucide-react'
import { Panel, SectionHeader } from '@/components/shared/MetricCard'
import type { TimeSeriesPoint } from '@/types'
import clsx from 'clsx'

interface Props {
  timeSeries: TimeSeriesPoint[]
  currentQueue: number
  emergencyQueueLength: number
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-surface-3 border border-surface-border rounded-lg p-2.5 text-xs shadow-xl">
      <div className="text-text-muted font-mono mb-1">Step {label}</div>
      {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
      {payload.map((p: any) => (
        <div key={p.dataKey} className="flex items-center justify-between gap-4">
          <span className="text-text-secondary">{p.name}</span>
          <span className="font-mono font-bold text-text-primary">{p.value}</span>
        </div>
      ))}
    </div>
  )
}

const QUEUE_LEVELS = [
  { threshold: 0, label: 'Clear', color: 'text-status-ok bg-status-ok/10 border-status-ok/20' },
  { threshold: 3, label: 'Moderate', color: 'text-status-warn bg-status-warn/10 border-status-warn/20' },
  { threshold: 7, label: 'High', color: 'text-orange-400 bg-orange-500/10 border-orange-500/20' },
  { threshold: 12, label: 'Critical', color: 'text-status-critical bg-status-critical/10 border-status-critical/20' },
]

function getQueueLevel(q: number) {
  if (q >= 12) return QUEUE_LEVELS[3]
  if (q >= 7) return QUEUE_LEVELS[2]
  if (q >= 3) return QUEUE_LEVELS[1]
  return QUEUE_LEVELS[0]
}

export function EmergencyQueuePanel({ timeSeries, emergencyQueueLength }: Props) {
  const queueLevel = getQueueLevel(emergencyQueueLength)
  const data = timeSeries.map((p) => ({
    step: p.step,
    queue: p.queue_length,
    arrivals: p.arrivals,
  }))

  return (
    <Panel className="h-full">
      <SectionHeader
        title="Emergency Queue"
        subtitle="Queue depth & arrival rate per step"
        className="mb-4"
        actions={
          <span className={clsx('inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-bold border', queueLevel.color)}>
            <AlertTriangle className="w-3 h-3" />
            {queueLevel.label}
          </span>
        }
      />

      {/* Current queue indicator */}
      <div className="flex items-center gap-4 mb-4 p-3 bg-surface-3 rounded-lg border border-surface-border">
        <div className="text-3xl font-bold tabular-nums text-text-primary">{emergencyQueueLength}</div>
        <div className="space-y-0.5">
          <div className="text-xs font-medium text-text-secondary">patients awaiting triage</div>
          <div className="flex items-center gap-1.5 text-[10px] text-text-muted">
            <Clock className="w-3 h-3" />
            Estimated wait: ~{Math.max(3, emergencyQueueLength * 4)} min
          </div>
        </div>
        {/* Visual queue blocks */}
        <div className="flex-1 flex items-end gap-0.5 h-8 ml-2">
          {Array.from({ length: Math.min(emergencyQueueLength, 15) }).map((_, i) => (
            <div
              key={i}
              className="flex-1 rounded-sm"
              style={{
                background: i < 3 ? '#10b981' : i < 7 ? '#f59e0b' : i < 12 ? '#f97316' : '#ef4444',
                height: `${60 + i * 3}%`,
              }}
            />
          ))}
          {emergencyQueueLength > 15 && (
            <span className="text-[10px] text-text-muted ml-1 self-center">+{emergencyQueueLength - 15}</span>
          )}
        </div>
      </div>

      <ResponsiveContainer width="100%" height={160}>
        <BarChart data={data} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1e2d4a" />
          <XAxis dataKey="step" tick={{ fill: '#475569', fontSize: 11 }} tickLine={false} axisLine={false} />
          <YAxis tick={{ fill: '#475569', fontSize: 11 }} tickLine={false} axisLine={false} />
          <Tooltip content={<CustomTooltip />} />
          <Bar dataKey="arrivals" name="Arrivals" fill="#0080ff" opacity={0.7} radius={[2, 2, 0, 0]} />
          <Bar dataKey="queue" name="Queue" fill="#f59e0b" opacity={0.8} radius={[2, 2, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </Panel>
  )
}

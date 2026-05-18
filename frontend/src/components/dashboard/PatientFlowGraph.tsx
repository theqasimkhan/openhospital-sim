'use client'

import {
  ComposedChart,
  Line,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts'
import { Panel, SectionHeader } from '@/components/shared/MetricCard'
import type { TimeSeriesPoint } from '@/types'

interface Props {
  timeSeries: TimeSeriesPoint[]
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-surface-3 border border-surface-border rounded-lg p-3 text-xs shadow-xl space-y-1">
      <div className="text-text-muted font-mono mb-1.5">Step {label}</div>
      {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
      {payload.map((p: any) => (
        <div key={p.dataKey} className="flex items-center justify-between gap-6">
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full" style={{ background: p.color }} />
            <span className="text-text-secondary">{p.name}</span>
          </span>
          <span className="font-mono font-semibold text-text-primary">{p.value}</span>
        </div>
      ))}
    </div>
  )
}

export function PatientFlowGraph({ timeSeries }: Props) {
  const data = timeSeries.map((p) => ({
    step: p.step,
    arrivals: p.arrivals,
    discharged: p.discharged,
    deceased: p.deceased,
    net: p.arrivals - p.discharged,
  }))

  return (
    <Panel>
      <SectionHeader
        title="Patient Flow"
        subtitle="Arrivals vs discharges vs mortality per step"
        className="mb-4"
        actions={
          <div className="flex items-center gap-3 text-[10px] font-medium text-text-muted">
            <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-brand-cyan" />Arrivals</span>
            <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-status-ok" />Discharged</span>
            <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-status-critical" />Deceased</span>
          </div>
        }
      />
      <ResponsiveContainer width="100%" height={220}>
        <ComposedChart data={data} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1e2d4a" />
          <XAxis dataKey="step" tick={{ fill: '#475569', fontSize: 11 }} tickLine={false} axisLine={false} />
          <YAxis tick={{ fill: '#475569', fontSize: 11 }} tickLine={false} axisLine={false} />
          <Tooltip content={<CustomTooltip />} />
          <Bar dataKey="arrivals" name="Arrivals" fill="#00d4ff" opacity={0.7} radius={[2, 2, 0, 0]} />
          <Bar dataKey="discharged" name="Discharged" fill="#10b981" opacity={0.7} radius={[2, 2, 0, 0]} />
          <Bar dataKey="deceased" name="Deceased" fill="#ef4444" opacity={0.8} radius={[2, 2, 0, 0]} />
          <Line
            type="monotone"
            dataKey="net"
            name="Net Flow"
            stroke="#f59e0b"
            strokeWidth={2}
            dot={{ r: 3, fill: '#f59e0b' }}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </Panel>
  )
}

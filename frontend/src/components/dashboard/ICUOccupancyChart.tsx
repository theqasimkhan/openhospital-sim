'use client'

import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts'
import { Panel } from '@/components/shared/MetricCard'
import { SectionHeader } from '@/components/shared/MetricCard'
import type { TimeSeriesPoint } from '@/types'

interface Props {
  timeSeries: TimeSeriesPoint[]
  icuTotal: number
}

// eslint-disable-next-line 
const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-surface-3 border border-surface-border rounded-lg p-3 text-xs space-y-1.5 shadow-xl">
      <div className="text-text-muted font-mono">Step {label}</div>
      {/* eslint-disable-next-line  */}
      {payload.map((p: any) => (
        <div key={p.dataKey} className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full" style={{ background: p.color }} />
          <span className="text-text-secondary">{p.name}:</span>
          <span className="font-mono font-semibold text-text-primary">
            {typeof p.value === 'number' && p.dataKey.includes('util')
              ? `${(p.value * 100).toFixed(1)}%`
              : p.value}
          </span>
        </div>
      ))}
    </div>
  )
}

export function ICUOccupancyChart({ timeSeries, icuTotal }: Props) {
  const data = timeSeries.map((p) => ({
    step: p.step,
    icu_util: p.icu_utilization,
    ward_util: p.ward_utilization,
    label: `${Math.floor(p.simulation_time / 60)}h`,
  }))

  return (
    <Panel className="h-full">
      <SectionHeader
        title="Bed Utilization Over Time"
        subtitle="ICU & ward occupancy rate per simulation step"
        className="mb-4"
        actions={
          <div className="flex items-center gap-3 text-[10px] font-medium text-text-muted">
            <span className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-brand-cyan" />ICU
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-brand-blue" />Ward
            </span>
          </div>
        }
      />
      <ResponsiveContainer width="100%" height={220}>
        <AreaChart data={data} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
          <defs>
            <linearGradient id="icuGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#06B6D4" stopOpacity={0.3} />
              <stop offset="95%" stopColor="#06B6D4" stopOpacity={0} />
            </linearGradient>
            <linearGradient id="wardGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#2563EB" stopOpacity={0.25} />
              <stop offset="95%" stopColor="#2563EB" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#CBD5E1" />
          <XAxis dataKey="step" tick={{ fill: '#64748B', fontSize: 11 }} tickLine={false} axisLine={false} />
          <YAxis
            tickFormatter={(v) => `${(v * 100).toFixed(0)}%`}
            tick={{ fill: '#64748B', fontSize: 11 }}
            tickLine={false}
            axisLine={false}
            domain={[0, 1]}
          />
          <Tooltip content={<CustomTooltip />} />
          <ReferenceLine y={0.9} stroke="#EF4444" strokeDasharray="4 4" strokeWidth={1} label={{ value: '90%', fill: '#EF4444', fontSize: 10, position: 'insideTopRight' }} />
          <ReferenceLine y={0.75} stroke="#F59E0B" strokeDasharray="4 4" strokeWidth={1} label={{ value: '75%', fill: '#F59E0B', fontSize: 10, position: 'insideTopRight' }} />
          <Area
            type="monotone"
            dataKey="ward_util"
            name="Ward"
            stroke="#2563EB"
            strokeWidth={2}
            fill="url(#wardGrad)"
            dot={false}
            activeDot={{ r: 4, fill: '#2563EB' }}
          />
          <Area
            type="monotone"
            dataKey="icu_util"
            name="ICU"
            stroke="#06B6D4"
            strokeWidth={2}
            fill="url(#icuGrad)"
            dot={false}
            activeDot={{ r: 4, fill: '#06B6D4' }}
          />
        </AreaChart>
      </ResponsiveContainer>
    </Panel>
  )
}

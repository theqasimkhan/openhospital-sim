'use client'

import {
  RadarChart,
  Radar,
  PolarGrid,
  PolarAngleAxis,
  ResponsiveContainer,
  Tooltip,
} from 'recharts'
import { Panel, SectionHeader } from '@/components/shared/MetricCard'
import type { HospitalSnapshot } from '@/types'

interface Props {
  snapshot: HospitalSnapshot
}

export function StaffUtilizationChart({ snapshot }: Props) {
  const data = [
    { metric: 'Doctor\nWorkload', value: Math.round(snapshot.doctor_workload * 100) },
    { metric: 'Nurse\nWorkload', value: Math.round(snapshot.nurse_workload * 100) },
    { metric: 'Equipment', value: Math.round(snapshot.equipment_utilization * 100) },
    { metric: 'ICU\nCapacity', value: Math.round((snapshot.icu_occupancy / snapshot.icu_total_beds) * 100) },
    { metric: 'Ward\nCapacity', value: Math.round((snapshot.regular_bed_occupancy / snapshot.regular_total_beds) * 100) },
    { metric: 'Queue\nPressure', value: Math.min(100, Math.round((snapshot.emergency_queue_length / 15) * 100)) },
  ]

  const staffRows = [
    { label: 'Doctors on duty', value: `${snapshot.available_doctors} / ${snapshot.total_doctors}`, pct: snapshot.available_doctors / snapshot.total_doctors },
    { label: 'Nurses on duty', value: `${snapshot.available_nurses} / ${snapshot.total_nurses}`, pct: snapshot.available_nurses / snapshot.total_nurses },
    { label: 'Doctor workload index', value: `${(snapshot.doctor_workload * 100).toFixed(0)}%`, pct: snapshot.doctor_workload },
    { label: 'Nurse workload index', value: `${(snapshot.nurse_workload * 100).toFixed(0)}%`, pct: snapshot.nurse_workload },
  ]

  return (
    <Panel className="h-full">
      <SectionHeader
        title="Resource Utilization Radar"
        subtitle="Multi-dimensional hospital load profile"
        className="mb-4"
      />
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <ResponsiveContainer width="100%" height={200}>
          <RadarChart data={data}>
            <PolarGrid stroke="#1e2d4a" />
            <PolarAngleAxis
              dataKey="metric"
              tick={{ fill: '#94a3b8', fontSize: 10 }}
              tickLine={false}
            />
            <Radar
              name="Utilization"
              dataKey="value"
              stroke="#00d4ff"
              fill="#00d4ff"
              fillOpacity={0.15}
              strokeWidth={2}
            />
            <Tooltip
              contentStyle={{ background: '#141c2e', border: '1px solid #1e2d4a', borderRadius: 8, color: '#e2e8f0', fontSize: 12 }}
              formatter={(v: number) => [`${v}%`, 'Utilization']}
            />
          </RadarChart>
        </ResponsiveContainer>

        <div className="space-y-3 self-center">
          {staffRows.map((row) => {
            const color = row.pct >= 0.9 ? '#ef4444' : row.pct >= 0.75 ? '#f59e0b' : '#10b981'
            return (
              <div key={row.label} className="space-y-1">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-text-secondary">{row.label}</span>
                  <span className="font-mono font-semibold text-text-primary">{row.value}</span>
                </div>
                <div className="h-1.5 bg-surface-4 rounded-full overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all duration-700"
                    style={{ width: `${Math.min(row.pct * 100, 100)}%`, background: color }}
                  />
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </Panel>
  )
}

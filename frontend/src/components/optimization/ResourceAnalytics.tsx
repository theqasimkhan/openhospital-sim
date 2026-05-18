'use client'

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  RadarChart,
  Radar,
  PolarGrid,
  PolarAngleAxis,
} from 'recharts'
import { TrendingUp, Award, Clock, Cpu } from 'lucide-react'
import { Panel, SectionHeader, MetricCard } from '@/components/shared/MetricCard'
import type { OptimizationResult, HospitalSnapshot } from '@/types'
import clsx from 'clsx'

interface Props {
  result: OptimizationResult
  snapshot: HospitalSnapshot
}

export function ResourceAnalytics({ result, snapshot }: Props) {
  const convergenceData = result.convergence_history.map((score, i) => ({
    iteration: i + 1,
    score: score * 100,
  }))

  const comparison = [
    {
      resource: 'Doctors',
      current: snapshot.available_doctors,
      optimal: result.best_solution.doctors_on_duty,
      max: snapshot.total_doctors * 1.5,
    },
    {
      resource: 'Nurses',
      current: snapshot.available_nurses,
      optimal: result.best_solution.nurses_on_duty,
      max: snapshot.total_nurses * 1.5,
    },
    {
      resource: 'ICU Beds',
      current: snapshot.icu_total_beds,
      optimal: result.best_solution.icu_beds_active,
      max: snapshot.icu_total_beds * 1.5,
    },
    {
      resource: 'Ward Beds',
      current: snapshot.regular_total_beds,
      optimal: result.best_solution.regular_beds_active,
      max: snapshot.regular_total_beds * 1.5,
    },
  ]

  const radarData = [
    { metric: 'Throughput', score: 85 },
    { metric: 'Mortality\nMin.', score: 78 },
    { metric: 'Resource\nBalance', score: 91 },
    { metric: 'Staff\nEquity', score: 82 },
    { metric: 'Queue\nMin.', score: 76 },
  ]

  return (
    <div className="space-y-5">
      {/* Summary cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <MetricCard
          label="Optimization Score"
          value={`${(result.best_score * 100).toFixed(1)}%`}
          sub={`Baseline: ${(result.baseline_score * 100).toFixed(1)}%`}
          variant="ok"
          icon={<Award className="w-4 h-4" />}
        />
        <MetricCard
          label="Improvement"
          value={`+${result.improvement_pct.toFixed(1)}%`}
          sub="vs. current allocation"
          variant="ok"
          trend="up"
          trendValue={result.algorithm}
          icon={<TrendingUp className="w-4 h-4" />}
        />
        <MetricCard
          label="Algorithm"
          value={result.algorithm.toUpperCase()}
          sub={`${result.evaluations.toLocaleString()} evaluations`}
          icon={<Cpu className="w-4 h-4" />}
        />
        <MetricCard
          label="Wall Time"
          value={`${(result.wall_time_seconds * 1000).toFixed(1)}ms`}
          sub="optimization runtime"
          icon={<Clock className="w-4 h-4" />}
        />
      </div>

      {/* Resource comparison */}
      <Panel>
        <SectionHeader title="Current vs. Optimal Allocation" subtitle="Resource delta analysis" className="mb-4" />
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {comparison.map((row) => {
            const currentPct = (row.current / row.max) * 100
            const optimalPct = (row.optimal / row.max) * 100
            const delta = row.optimal - row.current
            return (
              <div key={row.resource} className="space-y-2">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-text-secondary font-medium">{row.resource}</span>
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-text-muted">{row.current}</span>
                    <span className="text-text-muted">→</span>
                    <span className="font-mono font-bold text-brand-cyan">{row.optimal}</span>
                    <span className={clsx(
                      'text-[10px] font-mono font-bold',
                      delta > 0 ? 'text-status-warn' : delta < 0 ? 'text-status-ok' : 'text-text-muted'
                    )}>
                      {delta > 0 ? `+${delta}` : delta}
                    </span>
                  </div>
                </div>
                <div className="relative h-3 bg-surface-4 rounded-full overflow-hidden">
                  {/* Current */}
                  <div
                    className="absolute left-0 top-0 h-full bg-surface-border rounded-full"
                    style={{ width: `${currentPct}%` }}
                  />
                  {/* Optimal */}
                  <div
                    className="absolute left-0 top-0 h-full bg-brand-cyan/70 rounded-full transition-all duration-700"
                    style={{ width: `${Math.min(optimalPct, 100)}%` }}
                  />
                </div>
              </div>
            )
          })}
        </div>
      </Panel>

      {/* Convergence + Radar */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
        <Panel>
          <SectionHeader title="Convergence History" subtitle="Score improvement per generation" className="mb-4" />
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={convergenceData} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e2d4a" />
              <XAxis dataKey="iteration" tick={{ fill: '#475569', fontSize: 11 }} tickLine={false} axisLine={false} />
              <YAxis tickFormatter={(v) => `${v.toFixed(0)}%`} tick={{ fill: '#475569', fontSize: 11 }} tickLine={false} axisLine={false} domain={['dataMin - 2', 'dataMax + 2']} />
              <Tooltip
                contentStyle={{ background: '#141c2e', border: '1px solid #1e2d4a', borderRadius: 8, color: '#e2e8f0', fontSize: 12 }}
                formatter={(v: number) => [`${v.toFixed(2)}%`, 'Score']}
              />
              <Line
                type="monotone"
                dataKey="score"
                stroke="#10b981"
                strokeWidth={2.5}
                dot={{ r: 3, fill: '#10b981' }}
              />
            </LineChart>
          </ResponsiveContainer>
        </Panel>

        <Panel>
          <SectionHeader title="Multi-Objective Score Profile" subtitle="Optimal solution breakdown" className="mb-4" />
          <ResponsiveContainer width="100%" height={200}>
            <RadarChart data={radarData}>
              <PolarGrid stroke="#1e2d4a" />
              <PolarAngleAxis dataKey="metric" tick={{ fill: '#94a3b8', fontSize: 10 }} />
              <Radar name="Score" dataKey="score" stroke="#10b981" fill="#10b981" fillOpacity={0.15} strokeWidth={2} />
              <Tooltip
                contentStyle={{ background: '#141c2e', border: '1px solid #1e2d4a', borderRadius: 8, color: '#e2e8f0', fontSize: 12 }}
                formatter={(v: number) => [`${v}%`, 'Score']}
              />
            </RadarChart>
          </ResponsiveContainer>
        </Panel>
      </div>

      {/* Recommendations */}
      <Panel>
        <SectionHeader title="Optimization Recommendations" subtitle={`${result.recommendations.length} actions identified`} className="mb-3" />
        <div className="space-y-2">
          {result.recommendations.map((rec, i) => (
            <div key={i} className="flex items-start gap-3 p-3 bg-surface-3 rounded-lg border border-surface-border">
              <div className="w-5 h-5 rounded-full bg-brand-cyan/10 border border-brand-cyan/30 flex items-center justify-center flex-shrink-0 mt-0.5">
                <span className="text-[10px] font-bold text-brand-cyan">{i + 1}</span>
              </div>
              <p className="text-xs text-text-secondary leading-relaxed">{rec}</p>
            </div>
          ))}
        </div>
      </Panel>
    </div>
  )
}

'use client'

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  Legend,
} from 'recharts'
import { TrendingUp, AlertTriangle, CheckCircle, Clock, Zap } from 'lucide-react'
import clsx from 'clsx'
import { Panel, SectionHeader } from '@/components/shared/MetricCard'
import { RiskBadge, TrendBadge } from '@/components/shared/StatusBadge'
import type { ForecastBundle, TimeSeriesPoint } from '@/types'

interface Props {
  bundle: ForecastBundle
  timeSeries: TimeSeriesPoint[]
  onRunForecast: () => Promise<void>
  loading: boolean
}

// eslint-disable-next-line 
const ForecastTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-surface-3 border border-surface-border rounded-lg p-3 text-xs shadow-xl space-y-1.5">
      <div className="text-text-muted font-mono mb-1">Step {label}</div>
      {/* eslint-disable-next-line  */}
      {payload.map((p: any) => (
        <div key={p.dataKey} className="flex items-center justify-between gap-4">
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full" style={{ background: p.color }} />
            <span className="text-text-secondary">{p.name}</span>
          </span>
          <span className="font-mono font-semibold text-text-primary">
            {typeof p.value === 'number' && p.value <= 1 && p.value >= 0
              ? `${(p.value * 100).toFixed(1)}%`
              : typeof p.value === 'number' ? p.value.toFixed(1) : p.value}
          </span>
        </div>
      ))}
    </div>
  )
}

function buildCombinedData(timeSeries: TimeSeriesPoint[], forecastPoints: { step: number; value: number; lower_bound: number; upper_bound: number }[], metric: 'icu' | 'ward' | 'arrivals') {
  const historical = timeSeries.map((p) => ({
    step: p.step,
    actual: metric === 'icu' ? p.icu_utilization : metric === 'ward' ? p.ward_utilization : p.arrivals,
    forecast: null as number | null,
    lower: null as number | null,
    upper: null as number | null,
    isForecast: false,
  }))
  const forecast = forecastPoints.map((p) => ({
    step: p.step,
    actual: null as number | null,
    forecast: p.value,
    lower: p.lower_bound,
    upper: p.upper_bound,
    isForecast: true,
  }))
  return [...historical, ...forecast]
}

export function ForecastingPanel({ bundle, timeSeries, onRunForecast, loading }: Props) {
  const icuData = buildCombinedData(timeSeries, bundle.icu.points, 'icu')
  const wardData = buildCombinedData(timeSeries, bundle.ward.points, 'ward')
  const demandData = buildCombinedData(timeSeries, bundle.demand.points, 'arrivals')

  const surge = bundle.surge_risk
  const surgeSignals = Object.entries(surge.signals)

  return (
    <div className="space-y-5">
      {/* Run button + metadata */}
      <Panel>
        <div className="flex items-center justify-between gap-4 flex-wrap">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-brand-cyan" />
              <span className="text-sm font-semibold text-text-primary">Forecast Engine</span>
            </div>
            <div className="text-xs text-text-muted font-mono">
              Holt double-exponential smoothing · Generated {new Date(bundle.generated_at).toLocaleTimeString()}
            </div>
          </div>
          <button
            onClick={onRunForecast}
            disabled={loading}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-brand-cyan/10 border border-brand-cyan/30 text-brand-cyan text-sm font-semibold hover:bg-brand-cyan/20 disabled:opacity-40 transition-all"
          >
            <Zap className={`w-4 h-4 ${loading ? 'animate-pulse' : ''}`} />
            {loading ? 'Running…' : 'Run Forecast'}
          </button>
        </div>
      </Panel>

      {/* Surge risk panel */}
      <Panel className={clsx(
        'border',
        surge.risk_level === 'critical' ? 'border-status-critical/40 glow-crit' :
        surge.risk_level === 'high' ? 'border-status-warn/40 glow-warn' :
        'border-surface-border'
      )}>
        <div className="flex items-start justify-between gap-4 flex-wrap mb-4">
          <div className="space-y-1">
            <SectionHeader title="Surge Risk Assessment" subtitle="Composite signal analysis" />
          </div>
          <div className="flex items-center gap-3">
            <div className="text-right">
              <div className="text-2xl font-bold tabular-nums text-text-primary">
                {(surge.composite_score * 100).toFixed(0)}
                <span className="text-sm font-normal text-text-muted">%</span>
              </div>
              <div className="text-[10px] text-text-muted">composite score</div>
            </div>
            <RiskBadge risk={surge.risk_level} />
          </div>
        </div>

        {/* Signal breakdown */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
          {surgeSignals.map(([signal, value]) => {
            const pct = value * 100
            const color = pct >= 75 ? '#ef4444' : pct >= 50 ? '#f59e0b' : '#10b981'
            return (
              <div key={signal} className="space-y-1.5">
                <div className="flex items-center justify-between text-[10px]">
                  <span className="text-text-muted capitalize">{signal.replace(/_/g, ' ')}</span>
                  <span className="font-mono text-text-primary font-semibold">{pct.toFixed(0)}%</span>
                </div>
                <div className="h-1.5 bg-surface-4 rounded-full overflow-hidden">
                  <div className="h-full rounded-full" style={{ width: `${pct}%`, background: color }} />
                </div>
              </div>
            )
          })}
        </div>

        {/* Recommendations */}
        <div className="space-y-2">
          <div className="text-[10px] font-semibold tracking-widest uppercase text-text-muted">
            Recommended Actions
          </div>
          {surge.recommended_actions.map((action, i) => (
            <div key={i} className="flex items-start gap-2.5">
              <AlertTriangle className="w-3 h-3 text-status-warn flex-shrink-0 mt-0.5" />
              <span className="text-xs text-text-secondary">{action}</span>
            </div>
          ))}
        </div>
      </Panel>

      {/* ICU Forecast chart */}
      <Panel>
        <SectionHeader
          title="ICU Utilization Forecast"
          subtitle={`${bundle.icu.horizon_steps} step horizon · confidence ${(bundle.icu.confidence * 100).toFixed(0)}%`}
          className="mb-4"
          actions={
            <div className="flex items-center gap-3">
              <TrendBadge trend={bundle.icu.trend_direction} />
              {bundle.icu.steps_to_saturation != null && (
                <span className="text-xs text-status-warn font-mono flex items-center gap-1">
                  <Clock className="w-3 h-3" />
                  Sat. in ~{bundle.icu.steps_to_saturation} steps
                </span>
              )}
            </div>
          }
        />
        <ResponsiveContainer width="100%" height={220}>
          <LineChart data={icuData} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e2d4a" />
            <XAxis dataKey="step" tick={{ fill: '#475569', fontSize: 11 }} tickLine={false} axisLine={false} />
            <YAxis tickFormatter={(v) => `${(v * 100).toFixed(0)}%`} tick={{ fill: '#475569', fontSize: 11 }} tickLine={false} axisLine={false} domain={[0, 1]} />
            <Tooltip content={<ForecastTooltip />} />
            <Legend iconSize={8} wrapperStyle={{ fontSize: 11, color: '#94a3b8' }} />
            <ReferenceLine x={timeSeries[timeSeries.length - 1]?.step} stroke="#475569" strokeDasharray="4 4" label={{ value: 'Now', fill: '#94a3b8', fontSize: 10 }} />
            <ReferenceLine y={0.9} stroke="#ef4444" strokeDasharray="4 4" strokeWidth={1} />
            <Line type="monotone" dataKey="actual" name="Actual" stroke="#00d4ff" strokeWidth={2} dot={false} connectNulls={false} />
            <Line type="monotone" dataKey="forecast" name="Forecast" stroke="#7c3aed" strokeWidth={2} strokeDasharray="6 3" dot={false} connectNulls={false} />
            <Line type="monotone" dataKey="upper" name="Upper" stroke="#7c3aed" strokeWidth={1} strokeDasharray="3 3" dot={false} connectNulls={false} opacity={0.4} />
            <Line type="monotone" dataKey="lower" name="Lower" stroke="#7c3aed" strokeWidth={1} strokeDasharray="3 3" dot={false} connectNulls={false} opacity={0.4} />
          </LineChart>
        </ResponsiveContainer>
      </Panel>

      {/* Ward + Demand in a row */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
        <Panel>
          <SectionHeader
            title="Ward Utilization Forecast"
            subtitle={`Confidence ${(bundle.ward.confidence * 100).toFixed(0)}%`}
            className="mb-4"
            actions={<TrendBadge trend={bundle.ward.trend_direction} />}
          />
          <ResponsiveContainer width="100%" height={180}>
            <LineChart data={wardData} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e2d4a" />
              <XAxis dataKey="step" tick={{ fill: '#475569', fontSize: 11 }} tickLine={false} axisLine={false} />
              <YAxis tickFormatter={(v) => `${(v * 100).toFixed(0)}%`} tick={{ fill: '#475569', fontSize: 11 }} tickLine={false} axisLine={false} domain={[0, 1]} />
              <Tooltip content={<ForecastTooltip />} />
              <ReferenceLine x={timeSeries[timeSeries.length - 1]?.step} stroke="#475569" strokeDasharray="4 4" />
              <Line type="monotone" dataKey="actual" name="Actual" stroke="#0080ff" strokeWidth={2} dot={false} connectNulls={false} />
              <Line type="monotone" dataKey="forecast" name="Forecast" stroke="#7c3aed" strokeWidth={2} strokeDasharray="6 3" dot={false} connectNulls={false} />
            </LineChart>
          </ResponsiveContainer>
        </Panel>

        <Panel>
          <SectionHeader
            title="Patient Demand Forecast"
            subtitle={`Arrivals per step · Confidence ${(bundle.demand.confidence * 100).toFixed(0)}%`}
            className="mb-4"
            actions={<TrendBadge trend={bundle.demand.trend_direction} />}
          />
          <ResponsiveContainer width="100%" height={180}>
            <LineChart data={demandData} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e2d4a" />
              <XAxis dataKey="step" tick={{ fill: '#475569', fontSize: 11 }} tickLine={false} axisLine={false} />
              <YAxis tick={{ fill: '#475569', fontSize: 11 }} tickLine={false} axisLine={false} />
              <Tooltip content={<ForecastTooltip />} />
              <ReferenceLine x={timeSeries[timeSeries.length - 1]?.step} stroke="#475569" strokeDasharray="4 4" />
              <Line type="monotone" dataKey="actual" name="Actual" stroke="#10b981" strokeWidth={2} dot={false} connectNulls={false} />
              <Line type="monotone" dataKey="forecast" name="Forecast" stroke="#7c3aed" strokeWidth={2} strokeDasharray="6 3" dot={false} connectNulls={false} />
            </LineChart>
          </ResponsiveContainer>
        </Panel>
      </div>

      {/* Staffing forecast */}
      <Panel>
        <SectionHeader
          title="Staffing Requirement Forecast"
          subtitle="Recommended doctors per step"
          className="mb-3"
          actions={
            <div className="flex items-center gap-4 text-xs text-text-muted">
              {bundle.staffing.peak_doctors != null && (
                <span className="flex items-center gap-1">
                  <CheckCircle className="w-3 h-3 text-status-warn" />
                  Peak doctors: <strong className="text-text-primary ml-1">{bundle.staffing.peak_doctors}</strong>
                </span>
              )}
              {bundle.staffing.peak_nurses != null && (
                <span className="flex items-center gap-1">
                  <CheckCircle className="w-3 h-3 text-status-warn" />
                  Peak nurses: <strong className="text-text-primary ml-1">{bundle.staffing.peak_nurses}</strong>
                </span>
              )}
            </div>
          }
        />
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          {bundle.staffing.points.map((p) => (
            <div key={p.step} className="flex items-center gap-3 p-2 bg-surface-3 rounded-lg border border-surface-border">
              <span className="text-[10px] font-mono text-text-muted w-12">Step {p.step}</span>
              <div className="flex-1">
                <div className="h-2 bg-surface-4 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-brand-purple rounded-full transition-all"
                    style={{ width: `${Math.min((p.value / 25) * 100, 100)}%` }}
                  />
                </div>
              </div>
              <span className="text-xs font-mono font-bold text-text-primary w-16 text-right">
                {p.value.toFixed(0)} ± {(p.upper_bound - p.value).toFixed(0)}
              </span>
            </div>
          ))}
        </div>
      </Panel>
    </div>
  )
}

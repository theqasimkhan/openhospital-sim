'use client'

import { useEffect, useState, useCallback, useRef } from 'react'
import { Play, Pause, SkipBack, SkipForward, FastForward, Film } from 'lucide-react'
import { AppShell } from '@/components/layout/AppShell'
import { Panel, SectionHeader } from '@/components/shared/MetricCard'
import { CapacityBar } from '@/components/shared/MetricCard'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine,
} from 'recharts'
import { fetchForecastTimeSeries, fetchSimulationEvents } from '@/lib/api'
import { MOCK_TIME_SERIES, MOCK_EVENTS } from '@/lib/mock-data'
import type { TimeSeriesPoint, SimulationEvent } from '@/types'
import clsx from 'clsx'

export default function ReplayPage() {
  const [timeSeries, setTimeSeries] = useState<TimeSeriesPoint[]>(MOCK_TIME_SERIES)
  const [events, setEvents] = useState<SimulationEvent[]>(MOCK_EVENTS)
  const [currentStep, setCurrentStep] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [speed, setSpeed] = useState(1)
  const intervalRef = useRef<NodeJS.Timeout | null>(null)

  useEffect(() => {
    Promise.all([fetchForecastTimeSeries(), fetchSimulationEvents({ limit: 500 })]).then(
      ([ts, evts]) => {
        setTimeSeries(ts)
        setEvents(evts)
      }
    )
  }, [])

  const maxStep = timeSeries.length - 1

  const tick = useCallback(() => {
    setCurrentStep((s) => {
      if (s >= maxStep) {
        setPlaying(false)
        return s
      }
      return s + 1
    })
  }, [maxStep])

  useEffect(() => {
    if (playing) {
      intervalRef.current = setInterval(tick, 1000 / speed)
    } else {
      if (intervalRef.current) clearInterval(intervalRef.current)
    }
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current)
    }
  }, [playing, speed, tick])

  const activePoint = timeSeries[currentStep]
  const activeEvents = events.filter((e) => e.step_number === (activePoint?.step ?? 1))

  const chartData = timeSeries.slice(0, currentStep + 1).map((p) => ({
    step: p.step,
    icu: p.icu_utilization,
    ward: p.ward_utilization,
    queue: p.queue_length,
    arrivals: p.arrivals,
  }))

  const EVENT_COLORS: Record<string, string> = {
    PATIENT_ARRIVED: '#06B6D4',
    ICU_TRANSFER: '#F59E0B',
    DISCHARGE: '#10B981',
    PATIENT_DEATH: '#EF4444',
    EMERGENCY_SPIKE: '#EF4444',
    STAFF_SHORTAGE: '#f97316',
    STAFF_RESTORED: '#10B981',
    TRIAGE_COMPLETE: '#2563EB',
    DOCTOR_ASSIGNED: '#10B981',
    TREATMENT_STARTED: '#10B981',
  }

  return (
    <AppShell
      title="Simulation Replay"
      subtitle="Step-by-step event playback · deterministic replay engine"
    >
      <div className="space-y-5 max-w-[1600px]">
        {/* Playback controls */}
        <Panel>
          <div className="flex items-center gap-4 flex-wrap">
            {/* Controls */}
            <div className="flex items-center gap-2">
              <button
                onClick={() => { setCurrentStep(0); setPlaying(false) }}
                className="w-8 h-8 flex items-center justify-center rounded-lg bg-surface-3 border border-surface-border text-text-secondary hover:text-text-primary transition-colors"
              >
                <SkipBack className="w-4 h-4" />
              </button>
              <button
                onClick={() => setCurrentStep((s) => Math.max(0, s - 1))}
                className="w-8 h-8 flex items-center justify-center rounded-lg bg-surface-3 border border-surface-border text-text-secondary hover:text-text-primary transition-colors"
              >
                <SkipBack className="w-3.5 h-3.5" />
              </button>
              <button
                onClick={() => setPlaying((p) => !p)}
                className={clsx(
                  'w-10 h-10 flex items-center justify-center rounded-lg border text-sm font-semibold transition-colors',
                  playing
                    ? 'bg-status-warn/10 border-status-warn/30 text-status-warn hover:bg-status-warn/20'
                    : 'bg-status-ok/10 border-status-ok/30 text-status-ok hover:bg-status-ok/20'
                )}
              >
                {playing ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
              </button>
              <button
                onClick={() => setCurrentStep((s) => Math.min(maxStep, s + 1))}
                className="w-8 h-8 flex items-center justify-center rounded-lg bg-surface-3 border border-surface-border text-text-secondary hover:text-text-primary transition-colors"
              >
                <SkipForward className="w-3.5 h-3.5" />
              </button>
              <button
                onClick={() => { setCurrentStep(maxStep); setPlaying(false) }}
                className="w-8 h-8 flex items-center justify-center rounded-lg bg-surface-3 border border-surface-border text-text-secondary hover:text-text-primary transition-colors"
              >
                <SkipForward className="w-4 h-4" />
              </button>
            </div>

            {/* Scrubber */}
            <div className="flex-1 min-w-[200px] space-y-1">
              <div className="relative">
                <div className="h-2 bg-surface-4 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-brand-cyan rounded-full transition-none"
                    style={{ width: `${maxStep > 0 ? (currentStep / maxStep) * 100 : 0}%` }}
                  />
                </div>
                <input
                  type="range"
                  min={0}
                  max={maxStep}
                  value={currentStep}
                  onChange={(e) => { setCurrentStep(Number(e.target.value)); setPlaying(false) }}
                  className="absolute inset-0 w-full opacity-0 cursor-pointer h-2"
                />
              </div>
              <div className="flex items-center justify-between text-[10px] font-mono text-text-muted">
                <span>Step {activePoint?.step ?? 0}</span>
                <span>T = {activePoint?.simulation_time ?? 0} min</span>
                <span>Step {maxStep}</span>
              </div>
            </div>

            {/* Speed */}
            <div className="flex items-center gap-1.5">
              <FastForward className="w-3.5 h-3.5 text-text-muted" />
              <span className="text-xs text-text-muted">Speed:</span>
              {[0.5, 1, 2, 4].map((s) => (
                <button
                  key={s}
                  onClick={() => setSpeed(s)}
                  className={clsx(
                    'px-2 py-1 rounded text-xs font-mono font-medium border transition-all',
                    speed === s
                      ? 'bg-brand-cyan/10 text-brand-cyan border-brand-cyan/30'
                      : 'bg-surface-3 text-text-muted border-surface-border hover:text-text-primary'
                  )}
                >
                  {s}x
                </button>
              ))}
            </div>
          </div>
        </Panel>

        {/* Live metrics at current step */}
        {activePoint && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <Panel className="text-center">
              <div className="text-[10px] uppercase tracking-widest text-text-muted mb-1">Arrivals</div>
              <div className="text-2xl font-bold text-brand-cyan tabular-nums">{activePoint.arrivals}</div>
            </Panel>
            <Panel className="text-center">
              <div className="text-[10px] uppercase tracking-widest text-text-muted mb-1">ICU Util.</div>
              <div className={clsx('text-2xl font-bold tabular-nums', activePoint.icu_utilization >= 0.9 ? 'text-status-critical' : activePoint.icu_utilization >= 0.75 ? 'text-status-warn' : 'text-status-ok')}>
                {(activePoint.icu_utilization * 100).toFixed(0)}%
              </div>
            </Panel>
            <Panel className="text-center">
              <div className="text-[10px] uppercase tracking-widest text-text-muted mb-1">Queue</div>
              <div className={clsx('text-2xl font-bold tabular-nums', activePoint.queue_length >= 10 ? 'text-status-critical' : activePoint.queue_length >= 5 ? 'text-status-warn' : 'text-text-primary')}>
                {activePoint.queue_length}
              </div>
            </Panel>
            <Panel className="text-center">
              <div className="text-[10px] uppercase tracking-widest text-text-muted mb-1">Discharged</div>
              <div className="text-2xl font-bold text-status-ok tabular-nums">{activePoint.discharged}</div>
            </Panel>
          </div>
        )}

        {/* Chart + events */}
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-5">
          <div className="xl:col-span-2">
            <Panel>
              <SectionHeader title="Replay Timeline" subtitle="Utilization & queue · animated playback" className="mb-4" />
              <ResponsiveContainer width="100%" height={260}>
                <LineChart data={chartData} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#CBD5E1" />
                  <XAxis dataKey="step" tick={{ fill: '#64748B', fontSize: 11 }} tickLine={false} axisLine={false} />
                  <YAxis yAxisId="left" tickFormatter={(v) => `${(v * 100).toFixed(0)}%`} tick={{ fill: '#64748B', fontSize: 11 }} tickLine={false} axisLine={false} domain={[0, 1]} />
                  <YAxis yAxisId="right" orientation="right" tick={{ fill: '#64748B', fontSize: 11 }} tickLine={false} axisLine={false} />
                  <Tooltip contentStyle={{ background: '#FFFFFF', border: '1px solid #CBD5E1', borderRadius: 8, color: '#0F172A', fontSize: 12 }} />
                  <ReferenceLine yAxisId="left" y={0.9} stroke="#EF4444" strokeDasharray="4 4" strokeWidth={1} />
                  {activePoint && (
                    <ReferenceLine xAxisId={undefined} x={activePoint.step} stroke="#06B6D4" strokeWidth={1.5} strokeDasharray="4 4" yAxisId="left" />
                  )}
                  <Line yAxisId="left" type="monotone" dataKey="icu" name="ICU Util." stroke="#06B6D4" strokeWidth={2} dot={false} />
                  <Line yAxisId="left" type="monotone" dataKey="ward" name="Ward Util." stroke="#2563EB" strokeWidth={2} dot={false} />
                  <Line yAxisId="right" type="monotone" dataKey="queue" name="Queue" stroke="#F59E0B" strokeWidth={1.5} dot={false} strokeDasharray="4 3" />
                  <Line yAxisId="right" type="monotone" dataKey="arrivals" name="Arrivals" stroke="#10B981" strokeWidth={1.5} dot={false} strokeDasharray="4 3" />
                </LineChart>
              </ResponsiveContainer>

              {/* Capacity bars for active step */}
              {activePoint && (
                <div className="mt-4 pt-4 border-t border-surface-border grid grid-cols-2 gap-3">
                  <CapacityBar label="ICU Utilization" value={Math.round(activePoint.icu_utilization * 100)} max={100} unit="%" />
                  <CapacityBar label="Ward Utilization" value={Math.round(activePoint.ward_utilization * 100)} max={100} unit="%" />
                </div>
              )}
            </Panel>
          </div>

          {/* Events at this step */}
          <Panel noPad className="flex flex-col">
            <div className="p-4 border-b border-surface-border flex-shrink-0">
              <SectionHeader
                title="Events at Step"
                subtitle={`${activeEvents.length} events · Step ${activePoint?.step ?? 0}`}
                actions={<Film className="w-4 h-4 text-text-muted" />}
              />
            </div>
            <div className="flex-1 overflow-y-auto p-3 space-y-1.5">
              {activeEvents.length === 0 && (
                <div className="text-center text-text-muted text-xs py-8">
                  {timeSeries.length === 0 ? 'No data loaded' : 'No events at this step'}
                </div>
              )}
              {activeEvents.map((e) => (
                <div
                  key={e.id}
                  className="flex items-start gap-2 p-2 rounded-md bg-surface-3 border border-surface-border animate-slide-in"
                >
                  <span
                    className="w-2 h-2 rounded-full flex-shrink-0 mt-1.5"
                    style={{ background: EVENT_COLORS[e.event_type] ?? '#64748B' }}
                  />
                  <div className="min-w-0">
                    <div className="text-[11px] font-semibold text-text-primary">
                      {e.event_type.replace(/_/g, ' ')}
                    </div>
                    {e.patient_id && (
                      <div className="text-[10px] font-mono text-text-muted">{e.patient_id}</div>
                    )}
                    <div className="text-[10px] font-mono text-text-muted">T={e.simulation_time}m</div>
                  </div>
                </div>
              ))}
            </div>
          </Panel>
        </div>
      </div>
    </AppShell>
  )
}

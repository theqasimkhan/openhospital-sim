'use client'

import { useState } from 'react'
import { Play, Square, RotateCcw, SkipForward, Settings, Zap } from 'lucide-react'
import clsx from 'clsx'
import { Panel, SectionHeader } from '@/components/shared/MetricCard'
import type { SimulationConfig, HospitalSnapshot } from '@/types'

interface Props {
  snapshot: HospitalSnapshot
  onStart: (config?: SimulationConfig) => Promise<void>
  onStep: (minutes: number) => Promise<void>
  onReset: () => Promise<void>
  loading: boolean
}

const STEP_PRESETS = [
  { label: '15 min', value: 15 },
  { label: '30 min', value: 30 },
  { label: '1 hr', value: 60 },
  { label: '2 hr', value: 120 },
  { label: '4 hr', value: 240 },
  { label: '1 day', value: 1440 },
]

export function SimulationControls({ snapshot, onStart, onStep, onReset, loading }: Props) {
  const [stepMinutes, setStepMinutes] = useState(60)
  const [showConfig, setShowConfig] = useState(false)
  const [config, setConfig] = useState<SimulationConfig>({
    seed: 42,
    icu_beds: 20,
    regular_beds: 80,
    num_doctors: 15,
    num_nurses: 40,
    num_equipment_units: 30,
    mean_inter_arrival_minutes: 10,
  })

  const isIdle = snapshot.status === 'IDLE'
  const isActive = snapshot.status === 'ACTIVE'

  return (
    <Panel>
      <SectionHeader
        title="Simulation Engine"
        subtitle={`Status: ${snapshot.status} · Step ${snapshot.step_number} · T=${snapshot.simulation_time}m`}
        className="mb-4"
        actions={
          <button
            onClick={() => setShowConfig(!showConfig)}
            className={clsx(
              'flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs font-medium transition-all',
              showConfig
                ? 'bg-brand-cyan/10 text-brand-cyan border border-brand-cyan/30'
                : 'bg-surface-3 text-text-secondary border border-surface-border hover:text-text-primary'
            )}
          >
            <Settings className="w-3.5 h-3.5" />
            Config
          </button>
        }
      />

      {/* Status indicator */}
      <div className="flex items-center gap-3 p-3 bg-surface-3 rounded-lg border border-surface-border mb-4">
        <div
          className={clsx(
            'w-3 h-3 rounded-full',
            isActive ? 'bg-status-ok animate-pulse-slow' :
            snapshot.status === 'COMPLETED' ? 'bg-status-info' :
            'bg-text-muted'
          )}
        />
        <div className="flex-1">
          <div className="text-sm font-semibold text-text-primary">{snapshot.status}</div>
          <div className="text-xs text-text-muted font-mono">
            {Math.floor(snapshot.simulation_time / 60)}h {snapshot.simulation_time % 60}m elapsed · {snapshot.patient_throughput} patients processed
          </div>
        </div>
        <div className="text-right">
          <div className="text-xs text-text-muted">ICU</div>
          <div className="text-sm font-bold font-mono text-brand-cyan">
            {snapshot.icu_occupancy}/{snapshot.icu_total_beds}
          </div>
        </div>
      </div>

      {/* Primary controls */}
      <div className="flex flex-wrap gap-2 mb-4">
        <button
          onClick={() => onStart(config)}
          disabled={loading || isActive}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-status-ok/10 border border-status-ok/30 text-status-ok text-sm font-semibold hover:bg-status-ok/20 disabled:opacity-40 disabled:cursor-not-allowed transition-all"
        >
          <Play className="w-4 h-4" />
          {isIdle ? 'Start Simulation' : 'Restart'}
        </button>

        <button
          onClick={() => onStep(stepMinutes)}
          disabled={loading || !isActive}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-brand-cyan/10 border border-brand-cyan/30 text-brand-cyan text-sm font-semibold hover:bg-brand-cyan/20 disabled:opacity-40 disabled:cursor-not-allowed transition-all"
        >
          <SkipForward className="w-4 h-4" />
          Step +{stepMinutes}m
        </button>

        <button
          onClick={onReset}
          disabled={loading}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-surface-3 border border-surface-border text-text-secondary text-sm font-semibold hover:text-text-primary hover:border-status-warn/40 disabled:opacity-40 disabled:cursor-not-allowed transition-all"
        >
          <RotateCcw className="w-4 h-4" />
          Reset
        </button>

        {loading && (
          <div className="flex items-center gap-2 px-3 py-2 text-xs text-text-muted">
            <Zap className="w-3.5 h-3.5 animate-pulse text-brand-cyan" />
            Processing...
          </div>
        )}
      </div>

      {/* Step size picker */}
      <div className="space-y-2">
        <div className="text-[10px] font-semibold tracking-widest uppercase text-text-muted">
          Step Duration
        </div>
        <div className="flex flex-wrap gap-1.5">
          {STEP_PRESETS.map((p) => (
            <button
              key={p.value}
              onClick={() => setStepMinutes(p.value)}
              className={clsx(
                'px-3 py-1.5 rounded-md text-xs font-medium border transition-all',
                stepMinutes === p.value
                  ? 'bg-brand-cyan/10 text-brand-cyan border-brand-cyan/30'
                  : 'bg-surface-3 text-text-secondary border-surface-border hover:text-text-primary'
              )}
            >
              {p.label}
            </button>
          ))}
          <input
            type="number"
            min={1}
            max={10080}
            value={stepMinutes}
            onChange={(e) => setStepMinutes(Number(e.target.value))}
            className="w-20 px-2 py-1.5 rounded-md text-xs font-mono bg-surface-3 border border-surface-border text-text-primary focus:border-brand-cyan/50 focus:outline-none"
            placeholder="min"
          />
        </div>
      </div>

      {/* Config panel */}
      {showConfig && (
        <div className="mt-4 pt-4 border-t border-surface-border space-y-3">
          <div className="text-[10px] font-semibold tracking-widest uppercase text-text-muted">
            Simulation Configuration
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            {(
              [
                ['seed', 'RNG Seed', 0, 9999],
                ['icu_beds', 'ICU Beds', 5, 100],
                ['regular_beds', 'Ward Beds', 20, 300],
                ['num_doctors', 'Doctors', 3, 50],
                ['num_nurses', 'Nurses', 10, 150],
                ['mean_inter_arrival_minutes', 'Arrival Interval (min)', 1, 60],
              ] as const
            ).map(([key, label, min, max]) => (
              <div key={key} className="space-y-1">
                <label className="text-[10px] text-text-muted">{label}</label>
                <input
                  type="number"
                  min={min}
                  max={max}
                  value={config[key as keyof SimulationConfig] ?? ''}
                  onChange={(e) =>
                    setConfig((c) => ({ ...c, [key]: Number(e.target.value) }))
                  }
                  className="w-full px-2 py-1.5 rounded-md text-xs font-mono bg-surface-3 border border-surface-border text-text-primary focus:border-brand-cyan/50 focus:outline-none"
                />
              </div>
            ))}
          </div>
        </div>
      )}
    </Panel>
  )
}

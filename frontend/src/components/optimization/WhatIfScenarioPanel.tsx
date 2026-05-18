'use client'

import { useState } from 'react'
import { Sliders, Play, BarChart2 } from 'lucide-react'
import { Panel, SectionHeader } from '@/components/shared/MetricCard'
import clsx from 'clsx'

interface ScenarioParam {
  id: string
  label: string
  min: number
  max: number
  step: number
  unit?: string
  value: number
}

interface Props {
  onRunOptimization: (algorithm: 'greedy' | 'genetic' | 'pso', maxIterations: number) => Promise<void>
  loading: boolean
  currentScore?: number
}

const ALGORITHMS = [
  { id: 'greedy' as const, label: 'Greedy', sub: 'Coord. descent · <5ms', color: 'text-status-ok border-status-ok/30 bg-status-ok/5' },
  { id: 'genetic' as const, label: 'Genetic', sub: 'Real-valued GA · ~20ms', color: 'text-brand-cyan border-brand-cyan/30 bg-brand-cyan/5' },
  { id: 'pso' as const, label: 'PSO', sub: 'Particle swarm · ~20ms', color: 'text-brand-purple border-brand-purple/30 bg-brand-purple/5' },
]

const DEFAULT_PARAMS: ScenarioParam[] = [
  { id: 'doctors', label: 'Doctors on duty', min: 3, max: 30, step: 1, value: 15 },
  { id: 'nurses', label: 'Nurses on duty', min: 10, max: 80, step: 1, value: 40 },
  { id: 'icu_beds', label: 'ICU beds active', min: 5, max: 40, step: 1, value: 20 },
  { id: 'regular_beds', label: 'Ward beds active', min: 20, max: 150, step: 5, value: 80 },
  { id: 'max_iterations', label: 'Max iterations', min: 20, max: 200, step: 10, value: 80 },
]

export function WhatIfScenarioPanel({ onRunOptimization, loading, currentScore }: Props) {
  const [algorithm, setAlgorithm] = useState<'greedy' | 'genetic' | 'pso'>('genetic')
  const [params, setParams] = useState<ScenarioParam[]>(DEFAULT_PARAMS)

  const updateParam = (id: string, value: number) => {
    setParams((prev) => prev.map((p) => (p.id === id ? { ...p, value } : p)))
  }

  const maxIter = params.find((p) => p.id === 'max_iterations')?.value ?? 80

  const handleRun = () => onRunOptimization(algorithm, maxIter)

  return (
    <Panel>
      <SectionHeader
        title="What-If Scenario Planner"
        subtitle="Configure constraints and run the optimization engine"
        className="mb-5"
        actions={
          <div className="flex items-center gap-2">
            <Sliders className="w-4 h-4 text-brand-cyan" />
            <span className="text-xs text-brand-cyan font-medium">Scenario Builder</span>
          </div>
        }
      />

      {/* Algorithm selector */}
      <div className="mb-5">
        <div className="text-[10px] font-semibold tracking-widest uppercase text-text-muted mb-2">
          Algorithm
        </div>
        <div className="grid grid-cols-3 gap-2">
          {ALGORITHMS.map((alg) => (
            <button
              key={alg.id}
              onClick={() => setAlgorithm(alg.id)}
              className={clsx(
                'p-3 rounded-lg border text-left transition-all',
                algorithm === alg.id ? alg.color : 'bg-surface-3 border-surface-border text-text-secondary'
              )}
            >
              <div className="text-sm font-bold">{alg.label}</div>
              <div className="text-[10px] mt-0.5 opacity-70">{alg.sub}</div>
            </button>
          ))}
        </div>
      </div>

      {/* Sliders */}
      <div className="space-y-4 mb-5">
        <div className="text-[10px] font-semibold tracking-widest uppercase text-text-muted">
          Scenario Parameters
        </div>
        {params.map((param) => {
          const pct = ((param.value - param.min) / (param.max - param.min)) * 100
          return (
            <div key={param.id} className="space-y-1.5">
              <div className="flex items-center justify-between text-xs">
                <span className="text-text-secondary">{param.label}</span>
                <span className="font-mono font-bold text-text-primary tabular-nums">
                  {param.value}{param.unit ?? ''}
                </span>
              </div>
              <div className="relative">
                <div className="h-2 bg-surface-4 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-brand-cyan/60 rounded-full transition-none"
                    style={{ width: `${pct}%` }}
                  />
                </div>
                <input
                  type="range"
                  min={param.min}
                  max={param.max}
                  step={param.step}
                  value={param.value}
                  onChange={(e) => updateParam(param.id, Number(e.target.value))}
                  className="absolute inset-0 w-full opacity-0 cursor-pointer h-2"
                />
              </div>
              <div className="flex items-center justify-between text-[10px] font-mono text-text-muted">
                <span>{param.min}</span>
                <span>{param.max}</span>
              </div>
            </div>
          )
        })}
      </div>

      {/* Score preview */}
      {currentScore != null && (
        <div className="mb-4 p-3 bg-surface-3 rounded-lg border border-surface-border flex items-center gap-3">
          <BarChart2 className="w-4 h-4 text-status-ok" />
          <div className="flex-1">
            <div className="text-xs text-text-secondary">Last optimization score</div>
            <div className="text-lg font-bold text-status-ok tabular-nums">
              {(currentScore * 100).toFixed(1)}%
            </div>
          </div>
        </div>
      )}

      {/* Run button */}
      <button
        onClick={handleRun}
        disabled={loading}
        className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-lg bg-brand-cyan/10 border border-brand-cyan/30 text-brand-cyan text-sm font-semibold hover:bg-brand-cyan/20 disabled:opacity-40 disabled:cursor-not-allowed transition-all"
      >
        <Play className={`w-4 h-4 ${loading ? 'animate-pulse' : ''}`} />
        {loading ? 'Optimizing…' : `Run ${algorithm.toUpperCase()} Optimization`}
      </button>
    </Panel>
  )
}

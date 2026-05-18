'use client'

import { useEffect, useState, useCallback } from 'react'
import { AppShell } from '@/components/layout/AppShell'
import { ResourceAnalytics } from '@/components/optimization/ResourceAnalytics'
import { WhatIfScenarioPanel } from '@/components/optimization/WhatIfScenarioPanel'
import { fetchLatestOptimization, runOptimization, fetchSimulationState } from '@/lib/api'
import { MOCK_OPTIMIZATION, MOCK_SNAPSHOT } from '@/lib/mock-data'
import type { OptimizationResult, HospitalSnapshot } from '@/types'

export default function OptimizationPage() {
  const [result, setResult] = useState<OptimizationResult>(MOCK_OPTIMIZATION)
  const [snapshot, setSnapshot] = useState<HospitalSnapshot>(MOCK_SNAPSHOT)
  const [loading, setLoading] = useState(false)

  const load = useCallback(async () => {
    const [r, s] = await Promise.all([fetchLatestOptimization(), fetchSimulationState()])
    setResult(r)
    setSnapshot(s)
  }, [])

  useEffect(() => { load() }, [load])

  const handleRunOptimization = async (
    algorithm: 'greedy' | 'genetic' | 'pso',
    maxIterations: number
  ) => {
    setLoading(true)
    const r = await runOptimization(algorithm, maxIterations)
    setResult(r)
    setLoading(false)
  }

  return (
    <AppShell
      title="Resource Optimization"
      subtitle="Greedy · Genetic Algorithm · Particle Swarm · Multi-objective scoring"
    >
      <div className="max-w-[1600px]">
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-5">
          {/* What-if panel */}
          <div>
            <WhatIfScenarioPanel
              onRunOptimization={handleRunOptimization}
              loading={loading}
              currentScore={result.best_score}
            />
          </div>

          {/* Analytics */}
          <div className="xl:col-span-2">
            <ResourceAnalytics result={result} snapshot={snapshot} />
          </div>
        </div>
      </div>
    </AppShell>
  )
}

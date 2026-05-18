'use client'

import { useEffect, useState, useCallback } from 'react'
import { AppShell } from '@/components/layout/AppShell'
import { ForecastingPanel } from '@/components/forecasting/ForecastingPanel'
import { fetchLatestForecast, runForecasting, fetchForecastTimeSeries } from '@/lib/api'
import { MOCK_FORECAST, MOCK_TIME_SERIES } from '@/lib/mock-data'
import type { ForecastBundle, TimeSeriesPoint } from '@/types'

export default function ForecastingPage() {
  const [bundle, setBundle] = useState<ForecastBundle>(MOCK_FORECAST)
  const [timeSeries, setTimeSeries] = useState<TimeSeriesPoint[]>(MOCK_TIME_SERIES)
  const [loading, setLoading] = useState(false)

  const load = useCallback(async () => {
    const [b, ts] = await Promise.all([fetchLatestForecast(), fetchForecastTimeSeries()])
    setBundle(b)
    setTimeSeries(ts)
  }, [])

  useEffect(() => { load() }, [load])

  const handleRunForecast = async () => {
    setLoading(true)
    const b = await runForecasting(12)
    setBundle(b)
    setLoading(false)
  }

  return (
    <AppShell
      title="Forecasting"
      subtitle="Holt exponential smoothing · ICU & demand projection"
    >
      <div className="max-w-[1600px]">
        <ForecastingPanel
          bundle={bundle}
          timeSeries={timeSeries}
          onRunForecast={handleRunForecast}
          loading={loading}
        />
      </div>
    </AppShell>
  )
}

'use client'

import { useEffect, useState } from 'react'
import { RefreshCw, AlertTriangle, CheckCircle2, Clock, Wifi, WifiOff } from 'lucide-react'
import clsx from 'clsx'
import { fetchHealth } from '@/lib/api'
import type { HealthResponse } from '@/types'

interface TopBarProps {
  title: string
  subtitle?: string
  actions?: React.ReactNode
}

export function TopBar({ title, subtitle, actions }: TopBarProps) {
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [time, setTime] = useState(new Date())
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    const poll = async () => {
      const h = await fetchHealth()
      setHealth(h)
    }
    poll()
    const healthInterval = setInterval(poll, 15000)
    const timeInterval = setInterval(() => setTime(new Date()), 1000)
    return () => {
      clearInterval(healthInterval)
      clearInterval(timeInterval)
    }
  }, [])

  const handleRefresh = async () => {
    setLoading(true)
    const h = await fetchHealth()
    setHealth(h)
    setTimeout(() => setLoading(false), 600)
  }

  const statusColor =
    health?.status === 'healthy'
      ? 'text-status-ok'
      : health?.status === 'degraded'
      ? 'text-status-warn'
      : 'text-status-critical'

  const StatusIcon =
    health?.status === 'healthy' ? CheckCircle2 : health ? AlertTriangle : WifiOff

  return (
    <header className="h-14 border-b border-surface-border bg-surface-1/80 backdrop-blur-sm sticky top-0 z-30 flex items-center px-6 gap-6">
      {/* Title */}
      <div className="flex-1 min-w-0">
        <div className="flex items-baseline gap-3">
          <h1 className="text-base font-semibold text-text-primary truncate">{title}</h1>
          {subtitle && (
            <span suppressHydrationWarning className="text-xs text-text-muted hidden sm:block">{subtitle}</span>
          )}
        </div>
      </div>

      {/* Actions */}
      {actions && <div className="flex items-center gap-2">{actions}</div>}

      {/* System status */}
      <div className="flex items-center gap-4 border-l border-surface-border pl-4">
        {/* Time */}
        <div className="flex items-center gap-1.5 text-text-muted">
          <Clock className="w-3.5 h-3.5" />
          <span suppressHydrationWarning className="text-xs font-mono tabular-nums">
            {time.toLocaleTimeString('en-US', { hour12: false })}
          </span>
        </div>

        {/* Backend health */}
        <div className="flex items-center gap-1.5">
          {health ? (
            <StatusIcon className={clsx('w-3.5 h-3.5', statusColor)} />
          ) : (
            <WifiOff className="w-3.5 h-3.5 text-text-muted" />
          )}
          <span className={clsx('text-xs font-medium hidden sm:block', statusColor)}>
            {health?.status ?? 'connecting'}
          </span>
        </div>

        {/* Latencies */}
        {health?.status === 'healthy' && (
          <div className="hidden lg:flex items-center gap-2 text-[10px] font-mono text-text-muted">
            <span className="flex items-center gap-1">
              <Wifi className="w-3 h-3" />
              PG {health.services.postgres.latency_ms.toFixed(1)}ms
            </span>
            <span>RD {health.services.redis.latency_ms.toFixed(1)}ms</span>
          </div>
        )}

        {/* Refresh */}
        <button
          onClick={handleRefresh}
          className="w-7 h-7 flex items-center justify-center rounded-md hover:bg-surface-3 text-text-muted hover:text-text-primary transition-colors"
        >
          <RefreshCw className={clsx('w-3.5 h-3.5', loading && 'animate-spin')} />
        </button>
      </div>
    </header>
  )
}

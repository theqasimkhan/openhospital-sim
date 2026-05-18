import clsx from 'clsx'
import type { AgentStatus, DecisionPriority } from '@/types'

// ─── Priority Badge ───────────────────────────────────────────────────────────

const PRIORITY_STYLES: Record<DecisionPriority, string> = {
  CRITICAL: 'bg-status-critical/15 text-status-critical border-status-critical/30',
  HIGH:     'bg-status-warn/15 text-status-warn border-status-warn/30',
  MEDIUM:   'bg-brand-blue/15 text-brand-blue border-brand-blue/30',
  LOW:      'bg-text-muted/15 text-text-secondary border-text-muted/20',
  INFO:     'bg-status-ok/15 text-status-ok border-status-ok/30',
}

export function PriorityBadge({ priority }: { priority: DecisionPriority }) {
  return (
    <span
      className={clsx(
        'inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold tracking-wider border',
        PRIORITY_STYLES[priority]
      )}
    >
      {priority}
    </span>
  )
}

// ─── Agent Status Badge ───────────────────────────────────────────────────────

const AGENT_STATUS_STYLES: Record<AgentStatus, string> = {
  ACTIVE:     'bg-status-ok/15 text-status-ok border-status-ok/30',
  IDLE:       'bg-text-muted/15 text-text-muted border-text-muted/20',
  OVERLOADED: 'bg-status-critical/15 text-status-critical border-status-critical/30',
  STANDBY:    'bg-brand-blue/15 text-brand-blue border-brand-blue/30',
  ALERT:      'bg-status-warn/15 text-status-warn border-status-warn/30',
}

const AGENT_STATUS_DOTS: Record<AgentStatus, string> = {
  ACTIVE:     'bg-status-ok',
  IDLE:       'bg-text-muted',
  OVERLOADED: 'bg-status-critical',
  STANDBY:    'bg-brand-blue',
  ALERT:      'bg-status-warn',
}

export function AgentStatusBadge({ status }: { status: AgentStatus }) {
  return (
    <span
      className={clsx(
        'inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] font-bold tracking-wider border',
        AGENT_STATUS_STYLES[status]
      )}
    >
      <span className={clsx('w-1.5 h-1.5 rounded-full', AGENT_STATUS_DOTS[status], status === 'ACTIVE' && 'animate-pulse-slow')} />
      {status}
    </span>
  )
}

// ─── Risk Level Badge ─────────────────────────────────────────────────────────

const RISK_STYLES = {
  low:      'bg-status-ok/15 text-status-ok border-status-ok/30',
  medium:   'bg-status-warn/15 text-status-warn border-status-warn/30',
  high:     'bg-orange-500/15 text-orange-400 border-orange-500/30',
  critical: 'bg-status-critical/15 text-status-critical border-status-critical/30',
}

export function RiskBadge({ risk }: { risk: 'low' | 'medium' | 'high' | 'critical' }) {
  return (
    <span
      className={clsx(
        'inline-flex items-center px-2.5 py-1 rounded-md text-xs font-bold tracking-widest uppercase border',
        RISK_STYLES[risk]
      )}
    >
      {risk}
    </span>
  )
}

// ─── Trend Badge ──────────────────────────────────────────────────────────────

export function TrendBadge({ trend }: { trend: string }) {
  const styles =
    trend === 'surge' ? 'text-status-critical' :
    trend === 'increasing' ? 'text-status-warn' :
    trend === 'stable' ? 'text-brand-blue' :
    'text-status-ok'
  const arrows: Record<string, string> = {
    surge: '↑↑',
    increasing: '↑',
    stable: '→',
    decreasing: '↓',
  }
  return (
    <span className={clsx('text-xs font-bold font-mono', styles)}>
      {arrows[trend] ?? '~'} {trend}
    </span>
  )
}

// ─── Inline Pulse Dot ─────────────────────────────────────────────────────────

export function PulseDot({ color = 'ok' }: { color?: 'ok' | 'warn' | 'critical' | 'info' }) {
  const c = { ok: 'bg-status-ok', warn: 'bg-status-warn', critical: 'bg-status-critical', info: 'bg-status-info' }
  return <span className={clsx('inline-block w-2 h-2 rounded-full', c[color], 'animate-pulse-slow')} />
}

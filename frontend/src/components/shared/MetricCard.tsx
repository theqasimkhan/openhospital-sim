import clsx from 'clsx'

interface MetricCardProps {
  label: string
  value: string | number
  sub?: string
  trend?: 'up' | 'down' | 'neutral'
  trendValue?: string
  variant?: 'default' | 'ok' | 'warn' | 'critical'
  icon?: React.ReactNode
  className?: string
}

export function MetricCard({
  label,
  value,
  sub,
  trend,
  trendValue,
  variant = 'default',
  icon,
  className,
}: MetricCardProps) {
  const borderVariant = {
    default: 'border-surface-border',
    ok: 'border-status-ok/30',
    warn: 'border-status-warn/30',
    critical: 'border-status-critical/30',
  }
  const glowVariant = {
    default: '',
    ok: 'glow-ok',
    warn: 'glow-warn',
    critical: 'glow-crit',
  }
  const valueColor = {
    default: 'text-text-primary',
    ok: 'text-status-ok',
    warn: 'text-status-warn',
    critical: 'text-status-critical',
  }
  const trendColor = {
    up: 'text-status-warn',
    down: 'text-status-ok',
    neutral: 'text-text-muted',
  }
  const trendIcon = { up: '↑', down: '↓', neutral: '—' }

  return (
    <div
      className={clsx(
        'bg-surface-2 border rounded-xl p-4 flex flex-col gap-3',
        borderVariant[variant],
        glowVariant[variant],
        className
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <span className="text-[10px] font-semibold tracking-widest uppercase text-text-secondary">
          {label}
        </span>
        {icon && <span className="text-text-muted">{icon}</span>}
      </div>
      <div className="flex items-end justify-between gap-2">
        <span className={clsx('text-2xl font-bold tabular-nums leading-none', valueColor[variant])}>
          {value}
        </span>
        {trend && trendValue && (
          <span className={clsx('text-xs font-mono font-semibold', trendColor[trend])}>
            {trendIcon[trend]} {trendValue}
          </span>
        )}
      </div>
      {sub && <span className="text-xs text-text-muted">{sub}</span>}
    </div>
  )
}

// ─── Capacity Bar ─────────────────────────────────────────────────────────────

interface CapacityBarProps {
  label: string
  value: number
  max: number
  unit?: string
  className?: string
}

export function CapacityBar({ label, value, max, unit = '', className }: CapacityBarProps) {
  const pct = max > 0 ? (value / max) * 100 : 0
  const color =
    pct >= 90 ? '#ef4444' :
    pct >= 75 ? '#f59e0b' :
    pct >= 50 ? '#00d4ff' :
    '#10b981'

  return (
    <div className={clsx('space-y-1.5', className)}>
      <div className="flex items-center justify-between text-xs">
        <span className="text-text-secondary font-medium">{label}</span>
        <span className="font-mono tabular-nums text-text-primary font-semibold">
          {value}{unit} / {max}{unit}
          <span className="text-text-muted ml-1">({pct.toFixed(0)}%)</span>
        </span>
      </div>
      <div className="h-2 bg-surface-4 rounded-full overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-700"
          style={{ width: `${Math.min(pct, 100)}%`, backgroundColor: color }}
        />
      </div>
    </div>
  )
}

// ─── Section Header ───────────────────────────────────────────────────────────

interface SectionHeaderProps {
  title: string
  subtitle?: string
  actions?: React.ReactNode
  className?: string
}

export function SectionHeader({ title, subtitle, actions, className }: SectionHeaderProps) {
  return (
    <div className={clsx('flex items-center justify-between gap-4', className)}>
      <div>
        <h2 className="text-sm font-semibold text-text-primary">{title}</h2>
        {subtitle && <p className="text-xs text-text-muted mt-0.5">{subtitle}</p>}
      </div>
      {actions && <div className="flex items-center gap-2 flex-shrink-0">{actions}</div>}
    </div>
  )
}

// ─── Panel wrapper ─────────────────────────────────────────────────────────────

interface PanelProps {
  children: React.ReactNode
  className?: string
  noPad?: boolean
}

export function Panel({ children, className, noPad }: PanelProps) {
  return (
    <div
      className={clsx(
        'bg-surface-2 border border-surface-border rounded-xl',
        !noPad && 'p-4',
        className
      )}
    >
      {children}
    </div>
  )
}

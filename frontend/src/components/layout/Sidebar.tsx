'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import {
  LayoutDashboard,
  FlaskConical,
  Bot,
  TrendingUp,
  Zap,
  History,
  Activity,
  ChevronRight,
} from 'lucide-react'
import clsx from 'clsx'

const NAV_ITEMS = [
  { href: '/dashboard', label: 'Dashboard', icon: LayoutDashboard, description: 'Live overview' },
  { href: '/simulation', label: 'Simulation', icon: FlaskConical, description: 'Engine controls' },
  { href: '/agents', label: 'Agents', icon: Bot, description: 'AI decision logs' },
  { href: '/forecasting', label: 'Forecasting', icon: TrendingUp, description: 'Demand & ICU' },
  { href: '/optimization', label: 'Optimization', icon: Zap, description: 'Resource allocator' },
  { href: '/replay', label: 'Replay', icon: History, description: 'Event playback' },
]

export function Sidebar() {
  const pathname = usePathname()

  return (
    <aside className="fixed left-0 top-0 bottom-0 w-[220px] bg-surface-1 border-r border-surface-border flex flex-col z-40">
      {/* Logo */}
      <div className="px-5 py-5 border-b border-surface-border">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-brand-cyan/10 border border-brand-cyan/30 flex items-center justify-center">
            <Activity className="w-4 h-4 text-brand-cyan" />
          </div>
          <div>
            <div className="text-sm font-bold text-text-primary leading-tight">OpenHospital</div>
            <div className="text-[10px] font-medium tracking-widest uppercase text-text-muted leading-tight">
              Sim Command
            </div>
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-1">
        {NAV_ITEMS.map((item) => {
          const isActive = pathname === item.href || pathname.startsWith(item.href + '/')
          return (
            <Link
              key={item.href}
              href={item.href}
              className={clsx(
                'group flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-150',
                isActive
                  ? 'bg-brand-cyan/10 text-brand-cyan border border-brand-cyan/20'
                  : 'text-text-secondary hover:text-text-primary hover:bg-surface-3 border border-transparent'
              )}
            >
              <item.icon
                className={clsx('w-4 h-4 flex-shrink-0', isActive ? 'text-brand-cyan' : 'text-text-muted group-hover:text-text-secondary')}
              />
              <div className="flex-1 min-w-0">
                <div className="truncate">{item.label}</div>
                <div className="text-[10px] text-text-muted truncate">{item.description}</div>
              </div>
              {isActive && <ChevronRight className="w-3 h-3 text-brand-cyan/60" />}
            </Link>
          )
        })}
      </nav>

      {/* Footer */}
      <div className="px-4 py-4 border-t border-surface-border">
        <div className="text-[10px] font-medium tracking-widest uppercase text-text-muted mb-2">
          System
        </div>
        <div className="flex items-center gap-2">
          <span className="w-1.5 h-1.5 rounded-full bg-status-ok animate-pulse-slow" />
          <span className="text-xs text-text-muted">Backend connected</span>
        </div>
        <div className="text-[10px] text-text-muted mt-1.5 font-mono">
          Phase 5 · v1.0.0
        </div>
      </div>
    </aside>
  )
}

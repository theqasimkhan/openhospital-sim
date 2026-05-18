import { Sidebar } from './Sidebar'
import { TopBar } from './TopBar'

interface AppShellProps {
  title: string
  subtitle?: string
  actions?: React.ReactNode
  children: React.ReactNode
}

export function AppShell({ title, subtitle, actions, children }: AppShellProps) {
  return (
    <div className="min-h-screen bg-surface bg-grid">
      <Sidebar />
      <div className="ml-[220px] flex flex-col min-h-screen">
        <TopBar title={title} subtitle={subtitle} actions={actions} />
        <main className="flex-1 p-6 animate-fade-in">{children}</main>
      </div>
    </div>
  )
}

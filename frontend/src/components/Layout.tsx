import { type ReactNode, useState } from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import {
  BrainCircuit,
  FlaskConical,
  GraduationCap,
  Activity,
  GitBranch,
  LayoutDashboard,
  Library,
  Menu,
  MessageSquare,
  Upload,
  X,
} from 'lucide-react'
import { cx } from '../lib/cx'
import { Badge } from './ui'

const navItems = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/upload', icon: Upload, label: 'Upload' },
  { to: '/chat', icon: MessageSquare, label: 'Chat' },
  { to: '/library', icon: Library, label: 'Library' },
  { to: '/study-tools', icon: FlaskConical, label: 'Study Tools' },
  { to: '/graph', icon: GitBranch, label: 'Graph Explorer' },
  { to: '/system', icon: Activity, label: 'System Status' },
]

export default function Layout({ children }: { children: ReactNode }) {
  const [mobileOpen, setMobileOpen] = useState(false)
  const location = useLocation()

  return (
    <div className="min-h-screen text-text-primary">
      {mobileOpen && (
        <button
          aria-label="Close navigation overlay"
          className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm md:hidden"
          onClick={() => setMobileOpen(false)}
        />
      )}

      <aside
        className={cx(
          'fixed left-0 top-0 z-50 flex h-dvh w-64 flex-col border-r border-white/10 bg-surface-850/95 p-4 shadow-2xl shadow-black/40 backdrop-blur-xl transition-transform duration-300 md:w-60 md:translate-x-0',
          mobileOpen ? 'translate-x-0' : '-translate-x-full',
        )}
      >
        <div className="mb-6 flex items-center gap-3 px-2">
          <div className="agent-pulse flex h-9 w-9 items-center justify-center rounded-lg gradient-bg text-surface-950 shadow-[0_0_26px_rgba(76,215,246,0.18)]">
            <BrainCircuit className="h-5 w-5" />
          </div>
          <div className="min-w-0">
            <p className="font-display text-xl font-bold gradient-text">StudyMate</p>
            <p className="text-[11px] font-medium uppercase text-text-muted">Precision Intelligence</p>
          </div>
          <button
            aria-label="Close navigation"
            className="ml-auto rounded-lg p-1.5 text-text-muted hover:bg-white/5 hover:text-white md:hidden"
            onClick={() => setMobileOpen(false)}
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <nav className="flex-1 space-y-1">
          {navItems.map(({ to, icon: Icon, label }) => {
            const isActive = to === '/' ? location.pathname === '/' : location.pathname.startsWith(to)

            return (
              <NavLink
                key={to}
                to={to}
                onClick={() => setMobileOpen(false)}
                className={cx(
                  'group flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-all duration-200 active:scale-[0.98]',
                  isActive
                    ? 'bg-accent-cyan/14 text-accent-cyan ring-1 ring-accent-cyan/18'
                    : 'text-text-secondary hover:bg-white/[0.05] hover:text-white',
                )}
              >
                <Icon
                  className={cx(
                    'h-[18px] w-[18px] transition-transform group-hover:scale-105',
                    isActive ? 'text-accent-cyan' : 'text-text-muted',
                  )}
                />
                <span className="truncate">{label}</span>
                {isActive && <span className="ml-auto h-1.5 w-1.5 rounded-full bg-accent-cyan" />}
              </NavLink>
            )
          })}
        </nav>

        <div className="mt-4 border-t border-white/10 pt-4">
          <div className="rounded-xl border border-white/10 bg-white/[0.035] p-3">
            <div className="mb-2 flex items-center gap-2">
              <GraduationCap className="h-4 w-4 text-accent-violet" />
              <span className="text-xs font-semibold text-white">Agentic Study OS</span>
            </div>
            <div className="flex flex-wrap gap-1.5">
              <Badge tone="violet">RAG</Badge>
              <Badge tone="cyan">Vision</Badge>
            </div>
          </div>
        </div>
      </aside>

      <div className="min-h-screen md:pl-60">
        <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-white/10 bg-surface-950/78 px-4 backdrop-blur-xl md:hidden">
          <button
            aria-label="Open navigation"
            className="rounded-lg p-2 text-text-secondary hover:bg-white/[0.06] hover:text-white"
            onClick={() => setMobileOpen(true)}
          >
            <Menu className="h-5 w-5" />
          </button>
          <div className="flex items-center gap-2">
            <div className="flex h-7 w-7 items-center justify-center rounded-lg gradient-bg text-surface-950">
              <BrainCircuit className="h-4 w-4" />
            </div>
            <span className="font-display text-base font-semibold text-white">StudyMate</span>
          </div>
        </header>

        <main className="min-h-[calc(100vh-3.5rem)] md:min-h-screen">{children}</main>
      </div>
    </div>
  )
}

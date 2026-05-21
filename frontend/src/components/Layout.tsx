import { type ReactNode, useState } from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import {
  LayoutDashboard,
  Upload,
  MessageSquare,
  Library,
  FlaskConical,
  GraduationCap,
  Menu,
  X,
} from 'lucide-react'

const navItems = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/upload', icon: Upload, label: 'Upload' },
  { to: '/chat', icon: MessageSquare, label: 'Chat' },
  { to: '/library', icon: Library, label: 'Library' },
  { to: '/study-tools', icon: FlaskConical, label: 'Study Tools' },
]

export default function Layout({ children }: { children: ReactNode }) {
  const [mobileOpen, setMobileOpen] = useState(false)
  const location = useLocation()

  return (
    <div className="flex min-h-screen">
      {/* ── Mobile overlay ── */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm md:hidden"
          onClick={() => setMobileOpen(false)}
        />
      )}

      {/* ── Sidebar ── */}
      <aside
        className={`
          fixed top-0 left-0 z-50 h-full w-64 glass-solid flex flex-col
          transition-transform duration-300 ease-out
          ${mobileOpen ? 'translate-x-0' : '-translate-x-full'}
          md:translate-x-0 md:static md:z-auto
        `}
      >
        {/* Logo */}
        <div className="flex items-center gap-3 px-6 py-6 border-b border-white/5">
          <div className="w-9 h-9 rounded-xl gradient-bg flex items-center justify-center shadow-lg shadow-violet-500/20">
            <GraduationCap className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-sm font-bold tracking-tight text-white">StudyMate</h1>
            <p className="text-[10px] font-medium text-text-muted uppercase tracking-widest">Agentic AI</p>
          </div>
          <button
            className="ml-auto md:hidden p-1 rounded-lg hover:bg-white/5"
            onClick={() => setMobileOpen(false)}
          >
            <X className="w-5 h-5 text-text-muted" />
          </button>
        </div>

        {/* Nav links */}
        <nav className="flex-1 px-3 py-4 space-y-1">
          {navItems.map(({ to, icon: Icon, label }) => {
            const isActive = to === '/' ? location.pathname === '/' : location.pathname.startsWith(to)
            return (
              <NavLink
                key={to}
                to={to}
                onClick={() => setMobileOpen(false)}
                className={`
                  flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium
                  transition-all duration-200 group
                  ${isActive
                    ? 'bg-gradient-to-r from-violet-500/15 to-cyan-500/10 text-white shadow-sm'
                    : 'text-text-secondary hover:text-white hover:bg-white/5'
                  }
                `}
              >
                <Icon className={`w-[18px] h-[18px] transition-colors ${isActive ? 'text-violet-400' : 'text-text-muted group-hover:text-text-secondary'}`} />
                {label}
                {isActive && (
                  <div className="ml-auto w-1.5 h-1.5 rounded-full bg-violet-400 animate-pulse-glow" />
                )}
              </NavLink>
            )
          })}
        </nav>

        {/* Footer */}
        <div className="px-4 py-4 border-t border-white/5">
          <div className="glass rounded-xl p-3 text-center">
            <p className="text-[11px] text-text-muted">Powered by</p>
            <p className="text-xs font-semibold gradient-text">Hybrid RAG + Agents</p>
          </div>
        </div>
      </aside>

      {/* ── Main Content ── */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Mobile header */}
        <header className="md:hidden flex items-center gap-3 px-4 py-3 glass-solid border-b border-white/5">
          <button
            className="p-2 rounded-lg hover:bg-white/5"
            onClick={() => setMobileOpen(true)}
          >
            <Menu className="w-5 h-5 text-text-secondary" />
          </button>
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg gradient-bg flex items-center justify-center">
              <GraduationCap className="w-4 h-4 text-white" />
            </div>
            <span className="text-sm font-bold text-white">StudyMate</span>
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-y-auto">
          {children}
        </main>
      </div>
    </div>
  )
}

import { Outlet, NavLink } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  LayoutDashboard, Hash, Globe, Play, Network,
  FileText, LogOut, Zap, ChevronRight, Shield
} from 'lucide-react'
import { useAuthStore } from '@/stores/authStore'
import { useScanStore } from '@/stores/scanStore'

const NAV_ITEMS = [
  { to: '/dashboard',    icon: LayoutDashboard, label: 'Dashboard'   },
  { to: '/scans',        icon: Play,            label: 'Scans'        },
  { to: '/parameters',  icon: Hash,            label: 'Parameters'  },
  { to: '/endpoints',   icon: Globe,           label: 'Endpoints'   },
  { to: '/visualization', icon: Network,       label: 'Visualization' },
  { to: '/reports',     icon: FileText,        label: 'Reports'     },
]

export default function AppLayout() {
  const { user, logout } = useAuthStore()
  const activeScans = useScanStore(s => s.activeScans)
  const activeScanCount = Object.keys(activeScans).length

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Sidebar */}
      <aside className="w-60 flex-shrink-0 bg-[#070F1C] border-r border-[#1E2A3A] flex flex-col">
        {/* Logo */}
        <div className="px-5 py-5 border-b border-[#1E2A3A]">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-center">
              <Zap size={16} className="text-cyan-400" />
            </div>
            <div>
              <p className="text-sm font-bold text-white tracking-tight">ParamX Hunter</p>
              <p className="text-[10px] text-slate-600 font-mono">v1.0.0</p>
            </div>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 px-3 py-4 space-y-0.5 overflow-y-auto">
          {NAV_ITEMS.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-all group ${
                  isActive
                    ? 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/20'
                    : 'text-slate-500 hover:text-slate-200 hover:bg-[#0D1520]'
                }`
              }
            >
              {({ isActive }) => (
                <>
                  <Icon size={15} className={isActive ? 'text-cyan-400' : 'text-slate-600 group-hover:text-slate-400'} />
                  <span className="font-medium">{label}</span>
                  {label === 'Scans' && activeScanCount > 0 && (
                    <span className="ml-auto text-[10px] bg-emerald-500/20 text-emerald-400 border border-emerald-500/20 rounded-full px-1.5 py-0.5 font-mono">
                      {activeScanCount}
                    </span>
                  )}
                  {isActive && <ChevronRight size={12} className="ml-auto text-cyan-400/50" />}
                </>
              )}
            </NavLink>
          ))}
        </nav>

        {/* User section */}
        <div className="px-3 py-4 border-t border-[#1E2A3A]">
          <div className="flex items-center gap-3 px-3 py-2.5 rounded-lg bg-[#0D1520]">
            <div className="w-7 h-7 rounded-full bg-gradient-to-br from-cyan-500 to-purple-600 flex items-center justify-center text-white text-xs font-bold flex-shrink-0">
              {(user?.username?.[0] ?? 'U').toUpperCase()}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-xs font-medium text-slate-200 truncate">{user?.username ?? 'User'}</p>
              <p className="text-[10px] text-slate-600 font-mono capitalize">{user?.role ?? 'analyst'}</p>
            </div>
            <button
              onClick={logout}
              className="text-slate-600 hover:text-red-400 transition-colors"
              title="Logout"
            >
              <LogOut size={14} />
            </button>
          </div>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-y-auto bg-[#050E1A]">
        <Outlet />
      </main>
    </div>
  )
}

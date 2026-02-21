import { NavLink, Link } from 'react-router-dom'
import { Plus, LayoutGrid, FileText, TrendingUp, Settings } from 'lucide-react'
import { cn } from '@/lib/utils'

const NAV_ITEMS = [
  { to: '/app', icon: Plus, label: 'Generate' },
  { to: '/app/campaigns', icon: LayoutGrid, label: 'Campaigns' },
  { to: '/app/content', icon: FileText, label: 'Content Studio' },
  { to: '/app/trending', icon: TrendingUp, label: 'Trending' },
  { to: '/app/settings', icon: Settings, label: 'Settings' },
]

export default function Sidebar() {
  return (
    <aside className="bg-white border-r border-gray-200 flex flex-col h-full">
      {/* Logo */}
      <Link to="/app" className="flex items-center gap-2.5 px-5 py-[18px] border-b border-gray-100 no-underline text-gray-900">
        <img src="/logo.svg" alt="onlyGen" className="w-8 h-8 flex-shrink-0" />
        <span className="text-base font-extrabold tracking-tight">onlyGen</span>
      </Link>

      {/* Navigation */}
      <nav className="flex-1 flex flex-col gap-0.5 p-4 px-2.5">
        {NAV_ITEMS.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/app'}
            className={({ isActive }) =>
              cn(
                'flex items-center gap-2.5 px-3 py-2.5 rounded-[10px] text-[13.5px] font-medium text-gray-500 transition-all duration-100 no-underline',
                isActive
                  ? 'bg-brand-50 text-brand font-semibold'
                  : 'hover:bg-surface-alt hover:text-gray-900'
              )
            }
          >
            <Icon size={18} />
            {label}
          </NavLink>
        ))}
      </nav>

      {/* User */}
      <div className="p-2.5 border-t border-gray-100">
        <div className="flex items-center gap-2.5 px-3 py-2 rounded-[10px] cursor-pointer hover:bg-surface-alt transition-colors">
          <div className="w-8 h-8 rounded-full bg-surface-alt border-2 border-gray-200 grid place-items-center text-xs text-gray-400 font-semibold">
            E
          </div>
          <div>
            <div className="text-[13px] font-semibold text-gray-900">Eliot</div>
            <div className="text-[11px] text-gray-400">Free plan</div>
          </div>
        </div>
      </div>
    </aside>
  )
}

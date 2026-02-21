import { Link, useLocation } from 'react-router-dom'
import { LayoutDashboard, TrendingUp, FileText, BarChart3, Settings, Plus } from 'lucide-react'
import { cn } from '@/lib/utils'

interface LayoutProps {
  children: React.ReactNode
}

const navigation = [
  { name: '🏠 Dashboard', href: '/', icon: LayoutDashboard },
  { name: '📈 Trend Signals', href: '/signals', icon: TrendingUp },
  { name: '🎨 Ad Campaigns', href: '/campaigns', icon: FileText },
  { name: '📊 Analytics', href: '/analytics', icon: BarChart3 },
  { name: '⚙️ Settings', href: '/settings', icon: Settings },
]

export default function Layout({ children }: LayoutProps) {
  const location = useLocation()

  return (
    <div className="min-h-screen bg-gradient-to-br from-purple-50 via-pink-50 to-orange-50">
      {/* Sidebar */}
      <div className="fixed inset-y-0 left-0 w-64 bg-gradient-to-b from-purple-600 to-pink-600 shadow-2xl">
        <div className="flex flex-col h-full">
          {/* Logo */}
          <div className="flex items-center h-16 px-6 border-b border-white/20">
            <h1 className="text-2xl font-black text-white tracking-tight">
              OnlyGen<span className="text-yellow-300">✨</span>
            </h1>
          </div>

          {/* Navigation */}
          <nav className="flex-1 px-4 py-6 space-y-1">
            {navigation.map((item) => {
              const isActive = location.pathname === item.href
              return (
                <Link
                  key={item.name}
                  to={item.href}
                  className={cn(
                    'flex items-center px-4 py-3 text-sm font-bold rounded-lg transition-all transform hover:scale-105',
                    isActive
                      ? 'bg-white text-purple-600 shadow-lg'
                      : 'text-white/90 hover:bg-white/20'
                  )}
                >
                  <item.icon className="w-5 h-5 mr-3" />
                  {item.name}
                </Link>
              )
            })}
          </nav>

          {/* Quick Action */}
          <div className="p-4 border-t border-white/20">
            <Link
              to="/onboarding"
              className="flex items-center justify-center w-full px-4 py-3 text-sm font-bold text-purple-600 bg-yellow-300 rounded-lg hover:bg-yellow-400 transition-all transform hover:scale-105 shadow-lg"
            >
              <Plus className="w-5 h-5 mr-2" />
              Add Brand 🚀
            </Link>
          </div>
        </div>
      </div>

      {/* Main content */}
      <div className="pl-64">
        <main className="p-8">
          {children}
        </main>
      </div>
    </div>
  )
}

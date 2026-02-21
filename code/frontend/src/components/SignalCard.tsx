import { TrendingUp, TrendingDown } from 'lucide-react'
import type { TrendSignal } from '@/lib/types'
import { formatPercent, formatNumber } from '@/lib/utils'
import { cn } from '@/lib/utils'

interface SignalCardProps {
  signal: TrendSignal
  onClick?: () => void
}

export default function SignalCard({ signal, onClick }: SignalCardProps) {
  const momentumPositive = signal.probability_momentum > 0

  return (
    <div
      onClick={onClick}
      className="glass-card rounded-lg p-6 hover:bg-white/10 transition-all cursor-pointer group"
    >
      <div className="flex items-start justify-between mb-4">
        <div className="flex-1">
          <h3 className="text-lg font-semibold text-white mb-2">{signal.title}</h3>
          {signal.category && (
            <span className="inline-block px-3 py-1 text-xs font-medium text-emerald-400 bg-emerald-500/20 rounded border border-emerald-500/30">
              {signal.category.toUpperCase()}
            </span>
          )}
        </div>
        <div className={cn(
          'flex items-center px-3 py-1 rounded text-sm font-semibold',
          momentumPositive 
            ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' 
            : 'bg-red-500/20 text-red-400 border border-red-500/30'
        )}>
          {momentumPositive ? <TrendingUp className="w-4 h-4 mr-1" /> : <TrendingDown className="w-4 h-4 mr-1" />}
          {formatPercent(Math.abs(signal.probability_momentum))}
        </div>
      </div>

      {/* Probability bar */}
      <div className="mb-4">
        <div className="flex justify-between text-sm text-gray-400 mb-2">
          <span>Probability</span>
          <span className="font-semibold text-white">{formatPercent(signal.probability)}</span>
        </div>
        <div className="w-full bg-white/5 rounded-full h-2 overflow-hidden">
          <div
            className="bg-gradient-to-r from-emerald-500 to-teal-400 h-2 rounded-full transition-all duration-500"
            style={{ width: `${signal.probability * 100}%` }}
          />
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 gap-4 text-sm">
        <div className="glass rounded-lg p-3">
          <span className="text-gray-400 text-xs">Volume</span>
          <p className="font-semibold text-white mt-1">${formatNumber(signal.volume)}</p>
        </div>
        <div className="glass rounded-lg p-3">
          <span className="text-gray-400 text-xs">Velocity</span>
          <p className="font-semibold text-white mt-1">{formatPercent(signal.volume_velocity)}</p>
        </div>
      </div>
    </div>
  )
}

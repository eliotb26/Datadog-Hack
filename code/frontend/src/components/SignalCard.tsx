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
      className="bg-white rounded-xl border-2 border-purple-200 p-6 hover:shadow-2xl hover:border-purple-400 transition-all cursor-pointer transform hover:scale-105"
    >
      <div className="flex items-start justify-between mb-4">
        <div className="flex-1">
          <h3 className="text-lg font-bold text-gray-900 mb-1">{signal.title}</h3>
          {signal.category && (
            <span className="inline-block px-3 py-1 text-xs font-bold text-purple-600 bg-purple-100 rounded-full">
              {signal.category.toUpperCase()} 🔥
            </span>
          )}
        </div>
        <div className={cn(
          'flex items-center px-3 py-1 rounded-full text-sm font-bold shadow-md',
          momentumPositive ? 'bg-green-500 text-white' : 'bg-red-500 text-white'
        )}>
          {momentumPositive ? <TrendingUp className="w-4 h-4 mr-1" /> : <TrendingDown className="w-4 h-4 mr-1" />}
          {formatPercent(Math.abs(signal.probability_momentum))}
        </div>
      </div>

      {/* Probability bar */}
      <div className="mb-4">
        <div className="flex justify-between text-sm text-gray-600 mb-2 font-semibold">
          <span>🎯 Probability</span>
          <span className="text-purple-600">{formatPercent(signal.probability)}</span>
        </div>
        <div className="w-full bg-gray-200 rounded-full h-3 overflow-hidden">
          <div
            className="bg-gradient-to-r from-purple-500 to-pink-500 h-3 rounded-full transition-all duration-500 shadow-inner"
            style={{ width: `${signal.probability * 100}%` }}
          />
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 gap-4 text-sm">
        <div className="bg-purple-50 rounded-lg p-3">
          <span className="text-gray-600 font-semibold">💰 Volume</span>
          <p className="font-black text-purple-600 text-lg">${formatNumber(signal.volume)}</p>
        </div>
        <div className="bg-pink-50 rounded-lg p-3">
          <span className="text-gray-600 font-semibold">⚡ Velocity</span>
          <p className="font-black text-pink-600 text-lg">{formatPercent(signal.volume_velocity)}</p>
        </div>
      </div>
    </div>
  )
}

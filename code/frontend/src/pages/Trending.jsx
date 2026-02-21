import { useState } from 'react'
import { TrendingUp, TrendingDown, ArrowUpRight, Search, SlidersHorizontal } from 'lucide-react'
import { cn, MOCK_SIGNALS } from '@/lib/utils'

const CATEGORIES = ['All', 'Macro', 'Regulation', 'Crypto', 'AI', 'Social', 'Fintech', 'Hardware']

export default function Trending() {
  const [selectedCategory, setSelectedCategory] = useState('All')
  const [searchQuery, setSearchQuery] = useState('')

  const filtered = MOCK_SIGNALS.filter(s => {
    const matchCat = selectedCategory === 'All' || s.category === selectedCategory
    const matchSearch = !searchQuery || s.name.toLowerCase().includes(searchQuery.toLowerCase())
    return matchCat && matchSearch
  })

  return (
    <div className="flex-1 overflow-y-auto custom-scrollbar">
      {/* Header */}
      <div className="px-8 pt-8 pb-6">
        <div className="flex items-center justify-between mb-1">
          <h1 className="text-2xl font-extrabold text-gray-900 tracking-tight">Trending Signals</h1>
          <span className="inline-flex items-center gap-1.5 px-3 py-[5px] rounded-full text-xs font-semibold bg-emerald-50 text-emerald-600">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 pulse-dot" />
            Live from Polymarket
          </span>
        </div>
        <p className="text-sm text-gray-500 mb-6">Real-time prediction market signals ranked by content relevance.</p>

        {/* Filters */}
        <div className="flex items-center gap-3">
          <div className="flex gap-1 p-1 bg-surface-alt rounded-lg overflow-x-auto">
            {CATEGORIES.map(cat => (
              <button
                key={cat}
                onClick={() => setSelectedCategory(cat)}
                className={cn(
                  'px-3 py-1.5 rounded-md text-xs font-semibold whitespace-nowrap transition-fast',
                  selectedCategory === cat ? 'bg-white text-gray-900 shadow-card' : 'text-gray-500 hover:text-gray-700'
                )}
              >
                {cat}
              </button>
            ))}
          </div>
          <div className="flex-1" />
          <div className="flex items-center gap-2 px-3 py-2 rounded-lg border border-gray-200 bg-white text-sm text-gray-400">
            <Search size={16} />
            <input
              type="text"
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              placeholder="Search signals..."
              className="border-none outline-none bg-transparent text-gray-900 placeholder:text-gray-400 text-sm w-40"
            />
          </div>
        </div>
      </div>

      {/* Signal cards grid */}
      <div className="px-8 pb-8">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {filtered.map((signal, i) => (
            <div
              key={signal.id}
              className="bg-white border border-gray-200 rounded-card p-5 hover:border-brand/30 hover:shadow-card-md hover:-translate-y-px cursor-pointer transition-all duration-200 fade-in"
            >
              <div className="flex items-start justify-between mb-3">
                <div className="flex-1 min-w-0">
                  <span className="inline-block px-2 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wider bg-surface-alt text-gray-500 mb-2">
                    {signal.category}
                  </span>
                  <h3 className="text-sm font-bold text-gray-900 leading-snug">{signal.name}</h3>
                </div>
                <ArrowUpRight size={16} className="text-gray-400 shrink-0 ml-3" />
              </div>

              <div className="flex items-center gap-4 mb-3">
                {/* Probability */}
                <div>
                  <span className="text-[11px] text-gray-400 font-medium">Probability</span>
                  <div className="text-lg font-extrabold text-gray-900">{signal.probability}%</div>
                </div>
                {/* Volume */}
                <div>
                  <span className="text-[11px] text-gray-400 font-medium">Volume</span>
                  <div className="text-sm font-bold text-gray-700">{signal.volume}</div>
                </div>
                {/* Change */}
                <div>
                  <span className="text-[11px] text-gray-400 font-medium">Change</span>
                  <div className={cn('flex items-center gap-1 text-sm font-bold', signal.change > 0 ? 'text-emerald-600' : 'text-red-500')}>
                    {signal.change > 0 ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
                    {signal.change > 0 ? '+' : ''}{signal.change}%
                  </div>
                </div>
                {/* Timeframe */}
                <div>
                  <span className="text-[11px] text-gray-400 font-medium">Window</span>
                  <div className="text-sm font-semibold text-gray-600">{signal.timeframe}</div>
                </div>
              </div>

              {/* Probability bar */}
              <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                <div
                  className={cn(
                    'h-full rounded-full progress-animate',
                    signal.probability >= 70 ? 'bg-brand' : signal.probability >= 40 ? 'bg-amber-500' : 'bg-gray-400'
                  )}
                  style={{ width: `${signal.probability}%` }}
                />
              </div>
            </div>
          ))}
        </div>

        {filtered.length === 0 && (
          <div className="text-center py-16 text-sm text-gray-400">No signals match your filters.</div>
        )}
      </div>
    </div>
  )
}

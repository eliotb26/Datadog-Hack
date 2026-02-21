import { useState, useEffect, useCallback, useMemo } from 'react'
import { TrendingUp, TrendingDown, ArrowUpRight, Search, RefreshCw, Loader2 } from 'lucide-react'
import { cn } from '@/lib/utils'
import { apiFetch, submitAndPoll } from '@/lib/api'

const DEFAULT_CATEGORIES = ['All']
const SIGNALS_CACHE_KEY = 'signals:list:v1'
const SIGNALS_CACHE_TTL_MS = 120_000

function normalizeCategory(category) {
  return String(category || 'general').trim().toLowerCase()
}

function toCategoryLabel(category) {
  const normalized = normalizeCategory(category)
  return normalized
    .split(/[^a-z0-9]+/i)
    .filter(Boolean)
    .map(part => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ') || 'General'
}

export default function Trending() {
  const [selectedCategory, setSelectedCategory] = useState('All')
  const [searchQuery, setSearchQuery] = useState('')
  const [signals, setSignals] = useState([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState('')

  const loadSignalsCache = () => {
    try {
      const raw = localStorage.getItem(SIGNALS_CACHE_KEY)
      if (!raw) return null
      const parsed = JSON.parse(raw)
      if (!Array.isArray(parsed?.data) || !parsed?.savedAt) return null
      if (Date.now() - parsed.savedAt > SIGNALS_CACHE_TTL_MS) return null
      return parsed.data
    } catch {
      return null
    }
  }

  const saveSignalsCache = (data) => {
    try {
      localStorage.setItem(
        SIGNALS_CACHE_KEY,
        JSON.stringify({ savedAt: Date.now(), data })
      )
    } catch {}
  }

  const fetchSignals = useCallback(async ({ showSpinner = true } = {}) => {
    try {
      if (showSpinner) setLoading(true)
      setError('')
      const data = await apiFetch('/api/signals?limit=50')
      const normalized = Array.isArray(data)
        ? data
        : Array.isArray(data?.signals)
        ? data.signals
        : []
      setSignals(normalized)
      saveSignalsCache(normalized)
    } catch (err) {
      setError(err.message)
    } finally {
      if (showSpinner) setLoading(false)
    }
  }, [])

  useEffect(() => {
    const cached = loadSignalsCache()
    if (cached) {
      setSignals(cached)
      setLoading(false)
      fetchSignals({ showSpinner: false })
      return
    }
    fetchSignals({ showSpinner: true })
  }, [fetchSignals])

  const handleRefresh = async () => {
    setRefreshing(true)
    setError('')
    try {
      await submitAndPoll(
        '/api/signals/refresh',
        {},
        { intervalMs: 3000, timeoutMs: 90_000 }
      )
      await fetchSignals({ showSpinner: false })
    } catch (err) {
      setError(err.message)
    } finally {
      setRefreshing(false)
    }
  }

  const filtered = signals.filter(s => {
    const signalCategory = normalizeCategory(s.category)
    const matchCat =
      selectedCategory === 'All' ||
      signalCategory === normalizeCategory(selectedCategory)
    const matchSearch =
      !searchQuery ||
      s.title?.toLowerCase().includes(searchQuery.toLowerCase())
    return matchCat && matchSearch
  })

  const categories = useMemo(() => {
    const fromSignals = Array.from(new Set(signals.map(s => toCategoryLabel(s.category))))
      .filter(Boolean)
      .sort((a, b) => a.localeCompare(b))
    return [...DEFAULT_CATEGORIES, ...fromSignals]
  }, [signals])

  return (
    <div className="flex-1 overflow-y-auto custom-scrollbar">
      <div className="px-8 pt-8 pb-6">
        <div className="flex items-center justify-between mb-1">
          <h1 className="text-2xl font-extrabold text-gray-900 tracking-tight">Trending Signals</h1>
          <div className="flex items-center gap-3">
            {signals.length > 0 && (
              <span className="inline-flex items-center gap-1.5 px-3 py-[5px] rounded-full text-xs font-semibold bg-emerald-50 text-emerald-600">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 pulse-dot" />
                Live from Polymarket
              </span>
            )}
            <button
              onClick={handleRefresh}
              disabled={refreshing}
              className="inline-flex items-center gap-1.5 px-3 py-[5px] rounded-full text-xs font-semibold border border-brand bg-brand/5 text-brand hover:bg-brand/10 disabled:opacity-50 transition-fast"
            >
              {refreshing
                ? <Loader2 size={12} className="animate-spin" />
                : <RefreshCw size={12} />}
              {refreshing ? 'Refreshing...' : 'Refresh'}
            </button>
          </div>
        </div>
        <p className="text-sm text-gray-500 mb-6">Real-time prediction market signals ranked by content relevance.</p>

        {error && (
          <p className="mb-4 text-sm text-red-600 bg-red-50 px-4 py-2 rounded-lg">{error}</p>
        )}

        <div className="flex items-center gap-3">
          <div className="flex gap-1 p-1 bg-surface-alt rounded-lg overflow-x-auto">
            {categories.map(cat => (
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

      <div className="px-8 pb-8">
        {loading ? (
          <div className="flex items-center justify-center py-24 text-gray-400">
            <Loader2 size={24} className="animate-spin mr-3" />
            <span className="text-sm">Loading signals...</span>
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {filtered.map((signal) => {
              const probPct = signal.probability_pct ?? Math.round(signal.probability * 100)
              const clampedPct = Math.max(0, Math.min(100, probPct))
              const momentum = signal.probability_momentum ?? 0
              const volumeFormatted = signal.volume >= 1_000_000
                ? `$${(signal.volume / 1_000_000).toFixed(1)}M`
                : signal.volume >= 1000
                ? `$${(signal.volume / 1000).toFixed(0)}K`
                : `$${Math.round(signal.volume)}`

              return (
                <div
                  key={signal.id}
                  className="bg-white border border-gray-200 rounded-card p-5 hover:border-brand/30 hover:shadow-card-md hover:-translate-y-px cursor-pointer transition-all duration-200 fade-in"
                >
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex-1 min-w-0">
                      <span className="inline-block px-2 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wider bg-surface-alt text-gray-500 mb-2">
                        {toCategoryLabel(signal.category)}
                      </span>
                      <h3 className="text-sm font-bold text-gray-900 leading-snug">{signal.title}</h3>
                    </div>
                    <ArrowUpRight size={16} className="text-gray-400 shrink-0 ml-3" />
                  </div>

                  <div className="flex items-center gap-4 mb-3">
                    <div>
                      <span className="text-[11px] text-gray-400 font-medium">Probability</span>
                      <div className="text-lg font-extrabold text-gray-900">{clampedPct}%</div>
                    </div>
                    <div>
                      <span className="text-[11px] text-gray-400 font-medium">Volume</span>
                      <div className="text-sm font-bold text-gray-700">{volumeFormatted}</div>
                    </div>
                    <div>
                      <span className="text-[11px] text-gray-400 font-medium">Momentum</span>
                      <div className={cn('flex items-center gap-1 text-sm font-bold', momentum > 0 ? 'text-emerald-600' : momentum < 0 ? 'text-red-500' : 'text-gray-400')}>
                        {momentum > 0 ? <TrendingUp size={14} /> : momentum < 0 ? <TrendingDown size={14} /> : null}
                        {momentum > 0 ? '+' : ''}{(momentum * 100).toFixed(1)}%
                      </div>
                    </div>
                    <div>
                      <span className="text-[11px] text-gray-400 font-medium">Velocity</span>
                      <div className="text-sm font-semibold text-gray-600">
                        {signal.volume_velocity != null ? `${(signal.volume_velocity * 100).toFixed(1)}%` : '-'}
                      </div>
                    </div>
                  </div>

                  <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                    <div
                      className={cn(
                        'h-full rounded-full progress-animate',
                        clampedPct >= 70 ? 'bg-brand' : clampedPct >= 40 ? 'bg-amber-500' : 'bg-gray-400'
                      )}
                      style={{ width: `${clampedPct}%` }}
                    />
                  </div>
                </div>
              )
            })}
          </div>
        )}

        {!loading && filtered.length === 0 && signals.length > 0 && (
          <div className="text-center py-16 text-sm text-gray-400">No signals match your filters.</div>
        )}

        {!loading && signals.length === 0 && !error && (
          <div className="text-center py-16">
            <p className="text-sm text-gray-400 mb-4">No signals yet. Refresh to pull live data from Polymarket.</p>
            <button
              onClick={handleRefresh}
              disabled={refreshing}
              className="inline-flex items-center gap-2 px-4 py-2.5 rounded-[10px] bg-brand text-white text-sm font-semibold hover:bg-brand-700 disabled:opacity-50 transition-fast"
            >
              {refreshing ? <Loader2 size={16} className="animate-spin" /> : <RefreshCw size={16} />}
              {refreshing ? 'Refreshing...' : 'Refresh Now'}
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

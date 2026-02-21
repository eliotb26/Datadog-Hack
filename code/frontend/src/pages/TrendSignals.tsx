import { useEffect, useState } from 'react'
import { RefreshCw } from 'lucide-react'
import { getSignals, refreshSignals } from '@/lib/api'
import type { TrendSignal } from '@/lib/types'
import SignalCard from '@/components/SignalCard'

export default function TrendSignals() {
  const [signals, setSignals] = useState<TrendSignal[]>([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)

  useEffect(() => {
    loadSignals()
  }, [])

  const loadSignals = async () => {
    try {
      const res = await getSignals()
      setSignals(res.data)
    } catch (error) {
      console.error('Failed to load signals:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleRefresh = async () => {
    setRefreshing(true)
    try {
      await refreshSignals()
      await loadSignals()
    } catch (error) {
      console.error('Failed to refresh signals:', error)
      alert('Failed to refresh signals')
    } finally {
      setRefreshing(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-500">Loading signals...</div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-4xl font-bold text-white mb-2">
            Trend Signals
          </h1>
          <p className="text-gray-400">Live prediction market data from Polymarket</p>
        </div>
        <button
          onClick={handleRefresh}
          disabled={refreshing}
          className="flex items-center px-6 py-3 bg-emerald-500 text-white rounded-lg hover:bg-emerald-600 disabled:opacity-50 font-semibold transition-colors"
        >
          <RefreshCw className={`w-5 h-5 mr-2 ${refreshing ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {/* Signals Grid */}
      {signals.length === 0 ? (
        <div className="glass-card rounded-lg p-12 text-center">
          <p className="text-gray-400 text-lg">No signals available. Click refresh to fetch from Polymarket.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {signals.map((signal) => (
            <SignalCard key={signal.id} signal={signal} />
          ))}
        </div>
      )}
    </div>
  )
}

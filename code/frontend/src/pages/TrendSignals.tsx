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
          <h1 className="text-4xl font-black text-transparent bg-clip-text bg-gradient-to-r from-purple-600 to-pink-600">
            Trend Signals 📈
          </h1>
          <p className="text-gray-600 mt-2 font-semibold">What's hot on Polymarket right now 🔥</p>
        </div>
        <button
          onClick={handleRefresh}
          disabled={refreshing}
          className="flex items-center px-6 py-3 bg-gradient-to-r from-purple-600 to-pink-600 text-white rounded-xl hover:shadow-xl disabled:opacity-50 font-bold transform hover:scale-105 transition-all"
        >
          <RefreshCw className={`w-5 h-5 mr-2 ${refreshing ? 'animate-spin' : ''}`} />
          Refresh 🔄
        </button>
      </div>

      {/* Signals Grid */}
      {signals.length === 0 ? (
        <div className="bg-gradient-to-br from-purple-100 to-pink-100 rounded-2xl border-2 border-purple-300 p-12 text-center">
          <p className="text-gray-700 font-bold text-lg">No signals yet! Click refresh to fetch the hottest trends 🚀</p>
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

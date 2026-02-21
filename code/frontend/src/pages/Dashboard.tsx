import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { TrendingUp, FileText, Activity, RefreshCw } from 'lucide-react'
import { getSignals, getCampaigns, getHealth, triggerFeedback } from '@/lib/api'
import type { TrendSignal, Campaign, HealthStatus } from '@/lib/types'
import SignalCard from '@/components/SignalCard'
import CampaignCard from '@/components/CampaignCard'

export default function Dashboard() {
  const [signals, setSignals] = useState<TrendSignal[]>([])
  const [campaigns, setCampaigns] = useState<Campaign[]>([])
  const [health, setHealth] = useState<HealthStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [feedbackLoading, setFeedbackLoading] = useState(false)

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    try {
      const [signalsRes, campaignsRes, healthRes] = await Promise.all([
        getSignals(),
        getCampaigns(),
        getHealth(),
      ])
      setSignals(signalsRes.data.slice(0, 3))
      setCampaigns(campaignsRes.data.slice(0, 6))
      setHealth(healthRes.data)
    } catch (error) {
      console.error('Failed to load dashboard data:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleTriggerFeedback = async () => {
    setFeedbackLoading(true)
    try {
      await triggerFeedback()
      alert('Feedback loop triggered successfully')
      loadData()
    } catch (error) {
      console.error('Failed to trigger feedback:', error)
      alert('Failed to trigger feedback loop')
    } finally {
      setFeedbackLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-500">Loading...</div>
      </div>
    )
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-4xl font-black text-transparent bg-clip-text bg-gradient-to-r from-purple-600 to-pink-600">
            Dashboard 🚀
          </h1>
          <p className="text-gray-600 mt-2 font-semibold">Your AI-powered ad content machine is LIVE!</p>
        </div>
        <button
          onClick={handleTriggerFeedback}
          disabled={feedbackLoading}
          className="flex items-center px-6 py-3 bg-gradient-to-r from-purple-600 to-pink-600 text-white rounded-xl hover:shadow-xl disabled:opacity-50 font-bold transform hover:scale-105 transition-all"
        >
          <RefreshCw className={`w-5 h-5 mr-2 ${feedbackLoading ? 'animate-spin' : ''}`} />
          Boost AI 🧠
        </button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="bg-gradient-to-br from-purple-500 to-purple-600 rounded-2xl p-6 text-white shadow-xl transform hover:scale-105 transition-all">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-bold opacity-90">🔥 Hot Signals</p>
              <p className="text-4xl font-black mt-2">{signals.length}</p>
            </div>
            <TrendingUp className="w-12 h-12 opacity-80" />
          </div>
        </div>

        <div className="bg-gradient-to-br from-pink-500 to-pink-600 rounded-2xl p-6 text-white shadow-xl transform hover:scale-105 transition-all">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-bold opacity-90">🎨 Total Ads</p>
              <p className="text-4xl font-black mt-2">{campaigns.length}</p>
            </div>
            <FileText className="w-12 h-12 opacity-80" />
          </div>
        </div>

        <div className="bg-gradient-to-br from-orange-500 to-orange-600 rounded-2xl p-6 text-white shadow-xl transform hover:scale-105 transition-all">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-bold opacity-90">⚡ System Status</p>
              <p className="text-2xl font-black mt-2">{health?.status || 'Unknown'} ✨</p>
            </div>
            <Activity className="w-12 h-12 opacity-80" />
          </div>
        </div>
      </div>

      {/* Active Signals */}
      <div>
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-2xl font-black text-gray-900">🔥 Trending Now</h2>
          <Link to="/signals" className="text-sm font-bold text-purple-600 hover:text-pink-600 transition-colors">
            See all trends →
          </Link>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {signals.map((signal) => (
            <SignalCard key={signal.id} signal={signal} />
          ))}
        </div>
      </div>

      {/* Recent Campaigns */}
      <div>
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-2xl font-black text-gray-900">🎨 Latest Ad Bangers</h2>
          <Link to="/campaigns" className="text-sm font-bold text-purple-600 hover:text-pink-600 transition-colors">
            View all ads →
          </Link>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {campaigns.map((campaign) => (
            <CampaignCard key={campaign.id} campaign={campaign} />
          ))}
        </div>
      </div>
    </div>
  )
}

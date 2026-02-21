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
          <h1 className="text-4xl font-bold text-white mb-2">
            Dashboard
          </h1>
          <p className="text-gray-400">AI-powered ad content generation platform</p>
        </div>
        <button
          onClick={handleTriggerFeedback}
          disabled={feedbackLoading}
          className="flex items-center px-6 py-3 bg-emerald-500 text-white rounded-lg hover:bg-emerald-600 disabled:opacity-50 font-semibold transition-colors"
        >
          <RefreshCw className={`w-5 h-5 mr-2 ${feedbackLoading ? 'animate-spin' : ''}`} />
          Trigger Feedback
        </button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="glass-card rounded-lg p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-400 mb-1">Active Signals</p>
              <p className="text-3xl font-bold text-white">{signals.length}</p>
            </div>
            <TrendingUp className="w-10 h-10 text-emerald-400" />
          </div>
        </div>

        <div className="glass-card rounded-lg p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-400 mb-1">Total Campaigns</p>
              <p className="text-3xl font-bold text-white">{campaigns.length}</p>
            </div>
            <FileText className="w-10 h-10 text-blue-400" />
          </div>
        </div>

        <div className="glass-card rounded-lg p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-400 mb-1">System Status</p>
              <p className="text-2xl font-bold text-emerald-400">{health?.status || 'Unknown'}</p>
            </div>
            <Activity className="w-10 h-10 text-purple-400" />
          </div>
        </div>
      </div>

      {/* Active Signals */}
      <div>
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-2xl font-semibold text-white">Active Trend Signals</h2>
          <Link to="/signals" className="text-sm font-medium text-emerald-400 hover:text-emerald-300 transition-colors">
            View all →
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
          <h2 className="text-2xl font-semibold text-white">Recent Campaigns</h2>
          <Link to="/campaigns" className="text-sm font-medium text-emerald-400 hover:text-emerald-300 transition-colors">
            View all →
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

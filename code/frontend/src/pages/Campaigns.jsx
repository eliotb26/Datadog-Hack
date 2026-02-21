import { useState, useEffect, useCallback } from 'react'
import { Search, Plus, Loader2, Image as ImageIcon } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { cn, CHANNEL_CONFIG } from '@/lib/utils'
import { apiFetch, API_BASE } from '@/lib/api'

const STATUS_STYLES = {
  active:    'bg-emerald-50 text-emerald-600',
  completed: 'bg-gray-100 text-gray-500',
  draft:     'bg-amber-50 text-amber-600',
  approved:  'bg-blue-50 text-blue-600',
  posted:    'bg-violet-50 text-violet-600',
}

export default function Campaigns() {
  const [filter, setFilter] = useState('all')
  const [searchQuery, setSearchQuery] = useState('')
  const [campaigns, setCampaigns] = useState([])
  const [metricsMap, setMetricsMap] = useState({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const navigate = useNavigate()

  const fetchCampaigns = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const data = await apiFetch('/api/campaigns?limit=100')
      setCampaigns(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchCampaigns()
  }, [fetchCampaigns])

  // Apply filters
  const filtered = campaigns.filter(c => {
    const matchStatus = filter === 'all' || c.status === filter
    const matchSearch =
      !searchQuery ||
      c.headline?.toLowerCase().includes(searchQuery.toLowerCase())
    return matchStatus && matchSearch
  })

  // Aggregate metrics per campaign
  const getMetrics = (campaign) => {
    const metrics = campaign.metrics || []
    const totalImpressions = metrics.reduce((s, m) => s + (m.impressions || 0), 0)
    const avgEngagement = metrics.length
      ? (metrics.reduce((s, m) => s + (m.engagement_rate || 0), 0) / metrics.length * 100).toFixed(1)
      : 0
    return { impressions: totalImpressions, engagement: avgEngagement }
  }

  return (
    <div className="flex-1 overflow-y-auto custom-scrollbar">
      {/* Header */}
      <div className="px-8 pt-8 pb-6">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-extrabold text-gray-900 tracking-tight">Campaigns</h1>
            <p className="text-sm text-gray-500 mt-1">Manage and track your generated campaigns.</p>
          </div>
          <button
            onClick={() => navigate('/')}
            className="inline-flex items-center gap-2 px-4 py-2.5 rounded-[10px] bg-brand text-white text-sm font-semibold hover:bg-brand-700 transition-fast"
          >
            <Plus size={16} />
            New Campaign
          </button>
        </div>

        {error && (
          <p className="mb-4 text-sm text-red-600 bg-red-50 px-4 py-2 rounded-lg">{error}</p>
        )}

        {/* Filters + search */}
        <div className="flex items-center gap-3">
          <div className="flex gap-1 p-1 bg-surface-alt rounded-lg">
            {['all', 'draft', 'approved', 'active', 'completed'].map(f => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={cn(
                  'px-3 py-1.5 rounded-md text-xs font-semibold capitalize transition-fast',
                  filter === f ? 'bg-white text-gray-900 shadow-card' : 'text-gray-500 hover:text-gray-700'
                )}
              >
                {f}
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
              placeholder="Search campaigns..."
              className="border-none outline-none bg-transparent text-gray-900 placeholder:text-gray-400 text-sm w-48"
            />
          </div>
        </div>
      </div>

      {/* Campaign table */}
      <div className="px-8 pb-8">
        {loading ? (
          <div className="flex items-center justify-center py-24 text-gray-400">
            <Loader2 size={24} className="animate-spin mr-3" />
            <span className="text-sm">Loading campaigns…</span>
          </div>
        ) : (
          <div className="bg-white rounded-card border border-gray-200 overflow-hidden">
            {/* Table header */}
            <div className="grid grid-cols-[1fr_100px_140px_120px_100px_100px] gap-4 px-6 py-3 border-b border-gray-100 bg-surface-alt">
              <span className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider">Campaign</span>
              <span className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider">Status</span>
              <span className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider">Confidence</span>
              <span className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider">Channel</span>
              <span className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider text-right">Impressions</span>
              <span className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider text-right">Engagement</span>
            </div>

            {/* Table rows */}
            {filtered.map((campaign) => {
              const { impressions, engagement } = getMetrics(campaign)
              const channel = campaign.channel_recommendation?.toLowerCase() || ''
              const chConfig = CHANNEL_CONFIG[channel]
              const confidencePct = Math.round((campaign.confidence_score || 0) * 100)

              return (
                <div
                  key={campaign.id}
                  className="grid grid-cols-[1fr_100px_140px_120px_100px_100px] gap-4 px-6 py-4 border-b border-gray-50 hover:bg-brand-50/30 cursor-pointer transition-fast"
                >
                  <div className="flex items-center gap-3">
                    {campaign.visual_asset_url ? (
                      <div className="w-10 h-10 rounded-lg overflow-hidden bg-gray-100 shrink-0 border border-gray-200">
                        <img 
                          src={`${API_BASE}${campaign.visual_asset_url}`} 
                          className="w-full h-full object-cover"
                          alt=""
                        />
                      </div>
                    ) : (
                      <div className="w-10 h-10 rounded-lg bg-gray-50 border border-dashed border-gray-200 flex items-center justify-center shrink-0">
                        <ImageIcon size={14} className="text-gray-300" />
                      </div>
                    )}
                    <div className="min-w-0">
                      <span className="text-sm font-semibold text-gray-900 truncate block">{campaign.headline}</span>
                      <span className="block text-[11px] text-gray-400 mt-0.5">
                        {campaign.created_at ? new Date(campaign.created_at).toLocaleDateString() : ''}
                      </span>
                    </div>
                  </div>
                  <div className="flex items-center">
                    <span className={cn(
                      'px-2 py-0.5 rounded text-[11px] font-semibold capitalize',
                      STATUS_STYLES[campaign.status] || STATUS_STYLES.draft
                    )}>
                      {campaign.status}
                    </span>
                  </div>
                  <div className="flex items-center">
                    <div className="flex items-center gap-2">
                      <div className="w-16 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                        <div
                          className={cn(
                            'h-full rounded-full',
                            confidencePct >= 80 ? 'bg-emerald-500' : confidencePct >= 60 ? 'bg-amber-500' : 'bg-gray-400'
                          )}
                          style={{ width: `${confidencePct}%` }}
                        />
                      </div>
                      <span className="text-xs font-semibold text-gray-700">{confidencePct}%</span>
                    </div>
                  </div>
                  <div className="flex items-center gap-1">
                    {chConfig ? (
                      <span className={cn('w-5 h-5 rounded grid place-items-center text-[9px] font-bold text-white', chConfig.bg)}>
                        {chConfig.abbr}
                      </span>
                    ) : (
                      <span className="text-xs text-gray-500 capitalize">{channel || '—'}</span>
                    )}
                  </div>
                  <span className="text-sm font-semibold text-gray-900 text-right flex items-center justify-end">
                    {impressions > 0 ? impressions.toLocaleString() : '—'}
                  </span>
                  <span className="text-sm font-semibold text-gray-900 text-right flex items-center justify-end">
                    {Number(engagement) > 0 ? `${engagement}%` : '—'}
                  </span>
                </div>
              )
            })}

            {filtered.length === 0 && (
              <div className="px-6 py-12 text-center text-sm text-gray-400">
                {campaigns.length === 0
                  ? 'No campaigns yet — generate your first campaign from the home page.'
                  : 'No campaigns match this filter.'}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

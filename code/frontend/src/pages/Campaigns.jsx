import { useState } from 'react'
import { Search, Filter, Plus } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { cn, MOCK_PAST_CAMPAIGNS, CHANNEL_CONFIG } from '@/lib/utils'
import ChannelBadge from '@/components/ChannelBadge'

const STATUS_STYLES = {
  active: 'bg-emerald-50 text-emerald-600',
  completed: 'bg-gray-100 text-gray-500',
  draft: 'bg-amber-50 text-amber-600',
}

export default function Campaigns() {
  const [filter, setFilter] = useState('all')
  const navigate = useNavigate()

  const filtered = filter === 'all'
    ? MOCK_PAST_CAMPAIGNS
    : MOCK_PAST_CAMPAIGNS.filter(c => c.status === filter)

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

        {/* Filters + search */}
        <div className="flex items-center gap-3">
          <div className="flex gap-1 p-1 bg-surface-alt rounded-lg">
            {['all', 'active', 'completed', 'draft'].map(f => (
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
              placeholder="Search campaigns..."
              className="border-none outline-none bg-transparent text-gray-900 placeholder:text-gray-400 text-sm w-48"
            />
          </div>
        </div>
      </div>

      {/* Campaign table */}
      <div className="px-8 pb-8">
        <div className="bg-white rounded-card border border-gray-200 overflow-hidden">
          {/* Table header */}
          <div className="grid grid-cols-[1fr_100px_140px_120px_100px_100px] gap-4 px-6 py-3 border-b border-gray-100 bg-surface-alt">
            <span className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider">Campaign</span>
            <span className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider">Status</span>
            <span className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider">Signal</span>
            <span className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider">Channels</span>
            <span className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider text-right">Impressions</span>
            <span className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider text-right">Engagement</span>
          </div>

          {/* Table rows */}
          {filtered.map((campaign) => (
            <div
              key={campaign.id}
              className="grid grid-cols-[1fr_100px_140px_120px_100px_100px] gap-4 px-6 py-4 border-b border-gray-50 hover:bg-brand-50/30 cursor-pointer transition-fast"
            >
              <div>
                <span className="text-sm font-semibold text-gray-900">{campaign.title}</span>
                <span className="block text-[11px] text-gray-400 mt-0.5">{campaign.created}</span>
              </div>
              <div className="flex items-center">
                <span className={cn('px-2 py-0.5 rounded text-[11px] font-semibold capitalize', STATUS_STYLES[campaign.status])}>
                  {campaign.status}
                </span>
              </div>
              <span className="text-xs text-gray-500 flex items-center">{campaign.signal}</span>
              <div className="flex items-center gap-1">
                {campaign.channels.map(ch => (
                  <span key={ch} className={cn('w-5 h-5 rounded grid place-items-center text-[9px] font-bold text-white', CHANNEL_CONFIG[ch]?.bg || 'bg-gray-400')}>
                    {CHANNEL_CONFIG[ch]?.abbr || '?'}
                  </span>
                ))}
              </div>
              <span className="text-sm font-semibold text-gray-900 text-right flex items-center justify-end">
                {campaign.impressions > 0 ? campaign.impressions.toLocaleString() : '—'}
              </span>
              <span className="text-sm font-semibold text-gray-900 text-right flex items-center justify-end">
                {campaign.engagement > 0 ? `${campaign.engagement}%` : '—'}
              </span>
            </div>
          ))}

          {filtered.length === 0 && (
            <div className="px-6 py-12 text-center text-sm text-gray-400">
              No campaigns match this filter.
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

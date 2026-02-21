import { Twitter, Linkedin, Instagram, Mail, Shield, ShieldAlert } from 'lucide-react'
import type { Campaign } from '@/lib/types'
import { formatPercent, formatDate } from '@/lib/utils'
import { cn } from '@/lib/utils'

interface CampaignCardProps {
  campaign: Campaign
  onClick?: () => void
}

const channelIcons = {
  twitter: Twitter,
  linkedin: Linkedin,
  instagram: Instagram,
  newsletter: Mail,
}

const statusColors = {
  draft: 'bg-gray-500/20 text-gray-300 border-gray-500/30',
  approved: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  posted: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
  completed: 'bg-purple-500/20 text-purple-400 border-purple-500/30',
}

export default function CampaignCard({ campaign, onClick }: CampaignCardProps) {
  const ChannelIcon = channelIcons[campaign.channel_recommendation]

  return (
    <div
      onClick={onClick}
      className="glass-card rounded-lg p-6 hover:bg-white/10 transition-all cursor-pointer group"
    >
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div className="flex-1">
          <h3 className="text-lg font-semibold text-white mb-2">{campaign.headline}</h3>
          <p className="text-sm text-gray-400 line-clamp-2">{campaign.body_copy}</p>
        </div>
      </div>

      {/* Visual preview */}
      {campaign.visual_asset_url && (
        <div className="mb-4 rounded-lg overflow-hidden glass h-32 flex items-center justify-center">
          <img
            src={campaign.visual_asset_url}
            alt="Campaign visual"
            className="max-h-full max-w-full object-contain"
          />
        </div>
      )}

      {/* Badges */}
      <div className="flex flex-wrap gap-2 mb-4">
        {/* Status */}
        <span className={cn('px-3 py-1 text-xs font-semibold rounded border', statusColors[campaign.status])}>
          {campaign.status.toUpperCase()}
        </span>

        {/* Channel */}
        <span className="flex items-center px-3 py-1 text-xs font-semibold bg-emerald-500/20 text-emerald-400 rounded border border-emerald-500/30">
          <ChannelIcon className="w-3 h-3 mr-1" />
          {campaign.channel_recommendation}
        </span>

        {/* Confidence */}
        <span className="px-3 py-1 text-xs font-semibold bg-blue-500/20 text-blue-400 rounded border border-blue-500/30">
          {formatPercent(campaign.confidence_score)}
        </span>

        {/* Safety */}
        {campaign.safety_score !== undefined && (
          <span className={cn(
            'flex items-center px-3 py-1 text-xs font-semibold rounded border',
            campaign.safety_passed 
              ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30' 
              : 'bg-red-500/20 text-red-400 border-red-500/30'
          )}>
            {campaign.safety_passed ? <Shield className="w-3 h-3 mr-1" /> : <ShieldAlert className="w-3 h-3 mr-1" />}
            {formatPercent(campaign.safety_score)}
          </span>
        )}
      </div>

      {/* Footer */}
      <div className="text-xs text-gray-500">
        {formatDate(campaign.created_at)}
      </div>
    </div>
  )
}

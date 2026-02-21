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
  draft: 'bg-yellow-100 text-yellow-700 border-yellow-300',
  approved: 'bg-blue-100 text-blue-700 border-blue-300',
  posted: 'bg-green-100 text-green-700 border-green-300',
  completed: 'bg-purple-100 text-purple-700 border-purple-300',
}

export default function CampaignCard({ campaign, onClick }: CampaignCardProps) {
  const ChannelIcon = channelIcons[campaign.channel_recommendation]

  return (
    <div
      onClick={onClick}
      className="bg-white rounded-xl border-2 border-pink-200 p-6 hover:shadow-2xl hover:border-pink-400 transition-all cursor-pointer transform hover:scale-105"
    >
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div className="flex-1">
          <h3 className="text-lg font-bold text-gray-900 mb-2">{campaign.headline} 🎯</h3>
          <p className="text-sm text-gray-600 line-clamp-2">{campaign.body_copy}</p>
        </div>
      </div>

      {/* Visual preview */}
      {campaign.visual_asset_url && (
        <div className="mb-4 rounded-xl overflow-hidden bg-gradient-to-br from-purple-100 to-pink-100 h-32 flex items-center justify-center border-2 border-purple-200">
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
        <span className={cn('px-3 py-1 text-xs font-bold rounded-full border-2', statusColors[campaign.status])}>
          {campaign.status.toUpperCase()} ✨
        </span>

        {/* Channel */}
        <span className="flex items-center px-3 py-1 text-xs font-bold bg-gradient-to-r from-purple-500 to-pink-500 text-white rounded-full shadow-md">
          <ChannelIcon className="w-3 h-3 mr-1" />
          {campaign.channel_recommendation}
        </span>

        {/* Confidence */}
        <span className="px-3 py-1 text-xs font-bold bg-orange-100 text-orange-700 rounded-full border-2 border-orange-300">
          {formatPercent(campaign.confidence_score)} 🔥
        </span>

        {/* Safety */}
        {campaign.safety_score !== undefined && (
          <span className={cn(
            'flex items-center px-3 py-1 text-xs font-bold rounded-full border-2',
            campaign.safety_passed ? 'bg-green-100 text-green-700 border-green-300' : 'bg-red-100 text-red-700 border-red-300'
          )}>
            {campaign.safety_passed ? <Shield className="w-3 h-3 mr-1" /> : <ShieldAlert className="w-3 h-3 mr-1" />}
            {formatPercent(campaign.safety_score)}
          </span>
        )}
      </div>

      {/* Footer */}
      <div className="text-xs text-gray-500 font-semibold">
        ⏰ Created {formatDate(campaign.created_at)}
      </div>
    </div>
  )
}

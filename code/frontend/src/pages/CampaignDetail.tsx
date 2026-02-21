import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, Twitter, Linkedin, Instagram, Mail, Shield, ShieldAlert } from 'lucide-react'
import { getCampaign, approveCampaign } from '@/lib/api'
import type { Campaign } from '@/lib/types'
import { formatPercent, formatDate } from '@/lib/utils'

const channelIcons = {
  twitter: Twitter,
  linkedin: Linkedin,
  instagram: Instagram,
  newsletter: Mail,
}

export default function CampaignDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [campaign, setCampaign] = useState<Campaign | null>(null)
  const [loading, setLoading] = useState(true)
  const [approving, setApproving] = useState(false)

  useEffect(() => {
    if (id) {
      loadCampaign(id)
    }
  }, [id])

  const loadCampaign = async (campaignId: string) => {
    try {
      const res = await getCampaign(campaignId)
      setCampaign(res.data)
    } catch (error) {
      console.error('Failed to load campaign:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleApprove = async () => {
    if (!id) return
    setApproving(true)
    try {
      await approveCampaign(id)
      alert('Campaign approved!')
      loadCampaign(id)
    } catch (error) {
      console.error('Failed to approve campaign:', error)
      alert('Failed to approve campaign')
    } finally {
      setApproving(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-500">Loading campaign...</div>
      </div>
    )
  }

  if (!campaign) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-500">Campaign not found</p>
      </div>
    )
  }

  const ChannelIcon = channelIcons[campaign.channel_recommendation]

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Back button */}
      <button
        onClick={() => navigate('/campaigns')}
        className="flex items-center text-gray-600 hover:text-gray-900"
      >
        <ArrowLeft className="w-4 h-4 mr-2" />
        Back to campaigns
      </button>

      {/* Header */}
      <div className="bg-white rounded-lg border border-gray-200 p-8">
        <div className="flex items-start justify-between mb-6">
          <div className="flex-1">
            <h1 className="text-3xl font-bold text-gray-900 mb-2">{campaign.headline}</h1>
            <p className="text-sm text-gray-500">Created {formatDate(campaign.created_at)}</p>
          </div>
          {campaign.status === 'draft' && (
            <button
              onClick={handleApprove}
              disabled={approving}
              className="px-6 py-3 bg-primary text-white rounded-lg hover:bg-primary/90 disabled:opacity-50"
            >
              {approving ? 'Approving...' : 'Approve Campaign'}
            </button>
          )}
        </div>

        {/* Badges */}
        <div className="flex flex-wrap gap-2 mb-6">
          <span className="flex items-center px-3 py-1 text-sm font-medium bg-primary/10 text-primary rounded">
            <ChannelIcon className="w-4 h-4 mr-2" />
            {campaign.channel_recommendation}
          </span>
          <span className="px-3 py-1 text-sm font-medium bg-gray-100 text-gray-700 rounded">
            {formatPercent(campaign.confidence_score)} confidence
          </span>
          {campaign.safety_score !== undefined && (
            <span className={`flex items-center px-3 py-1 text-sm font-medium rounded ${
              campaign.safety_passed ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
            }`}>
              {campaign.safety_passed ? <Shield className="w-4 h-4 mr-2" /> : <ShieldAlert className="w-4 h-4 mr-2" />}
              Safety: {formatPercent(campaign.safety_score)}
            </span>
          )}
        </div>

        {/* Body Copy */}
        <div className="mb-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-3">Body Copy</h2>
          <p className="text-gray-700 whitespace-pre-wrap">{campaign.body_copy}</p>
        </div>

        {/* Visual */}
        {campaign.visual_asset_url && (
          <div className="mb-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-3">Visual Asset</h2>
            <div className="rounded-lg overflow-hidden bg-gray-100 flex items-center justify-center p-8">
              <img
                src={campaign.visual_asset_url}
                alt="Campaign visual"
                className="max-w-full max-h-96 object-contain"
              />
            </div>
          </div>
        )}

        {/* Visual Direction */}
        <div className="mb-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-3">Visual Direction</h2>
          <p className="text-gray-700">{campaign.visual_direction}</p>
        </div>

        {/* Channel Reasoning */}
        <div>
          <h2 className="text-lg font-semibold text-gray-900 mb-3">Channel Recommendation</h2>
          <p className="text-gray-700">{campaign.channel_reasoning}</p>
        </div>
      </div>
    </div>
  )
}

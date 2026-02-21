export interface CompanyProfile {
  id: string
  name: string
  industry: string
  tone_of_voice?: string
  target_audience?: string
  campaign_goals?: string
  competitors: string[]
  content_history: string[]
  visual_style?: string
  safety_threshold: number
  created_at: string
  updated_at: string
}

export interface TrendSignal {
  id: string
  polymarket_market_id: string
  title: string
  category?: string
  probability: number
  probability_momentum: number
  volume: number
  volume_velocity: number
  relevance_scores: Record<string, number>
  confidence_score: number
  surfaced_at: string
  expires_at?: string
}

export interface Campaign {
  id: string
  company_id?: string
  trend_signal_id?: string
  headline: string
  body_copy: string
  visual_direction: string
  visual_asset_url?: string
  confidence_score: number
  channel_recommendation: 'twitter' | 'linkedin' | 'instagram' | 'newsletter'
  channel_reasoning: string
  safety_score?: number
  safety_passed: boolean
  status: 'draft' | 'approved' | 'posted' | 'completed'
  created_at: string
}

export interface CampaignMetrics {
  channel: string
  impressions: number
  clicks: number
  engagement_rate: number
  sentiment_score?: number
}

export interface HealthStatus {
  status: string
  dependencies: Record<string, string>
  uptime_seconds: number
}

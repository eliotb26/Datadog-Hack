import { clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

/** Merge Tailwind classes safely */
export function cn(...inputs) {
  return twMerge(clsx(inputs))
}

/**
 * Detect campaign info from user text input.
 * Returns an object with booleans for each category.
 */
export function detectCampaignInfo(text) {
  const t = text.toLowerCase()
  return {
    company:
      /\b(company|saas|fintech|startup|platform|product|we are|we're|our|software|app|tool|agency|brand|business)\b/.test(t) ||
      /\.(com|io|co|ai|org)\b/.test(t),
    audience:
      /\b(b2b|b2c|enterprise|smb|consumer|customer|developer|marketer|founder|cfo|cto|audience|target|user)\b/.test(t),
    goal:
      /\b(awareness|lead|launch|thought leadership|engagement|growth|conversion|traffic|revenue|sign.?up|brand)\b/.test(t),
    channel:
      /\b(linkedin|twitter|x |blog|newsletter|instagram|email|social|tiktok|youtube|reddit|channel)\b/.test(t),
  }
}

/**
 * Count how many info fields are completed.
 */
export function countCompleted(info) {
  return Object.values(info).filter(Boolean).length
}

/**
 * Format a confidence percentage with color class.
 */
export function confidenceColor(value) {
  if (value >= 80) return 'text-emerald-600'
  if (value >= 60) return 'text-amber-600'
  return 'text-red-500'
}

/**
 * Format a confidence bar fill color.
 */
export function confidenceBarColor(value) {
  if (value >= 80) return 'bg-emerald-500'
  if (value >= 60) return 'bg-amber-500'
  return 'bg-red-500'
}

/**
 * Channel icon config map.
 */
export const CHANNEL_CONFIG = {
  linkedin: { label: 'LinkedIn', abbr: 'in', bg: 'bg-[#0A66C2]' },
  twitter:  { label: 'Twitter/X', abbr: '𝕏', bg: 'bg-gray-900' },
  email:    { label: 'Newsletter', abbr: '@', bg: 'bg-teal' },
  blog:     { label: 'Blog', abbr: 'B', bg: 'bg-emerald-600' },
  instagram:{ label: 'Instagram', abbr: 'IG', bg: 'bg-pink-500' },
  youtube:  { label: 'YouTube', abbr: 'YT', bg: 'bg-red-600' },
  reddit:   { label: 'Reddit', abbr: 'R', bg: 'bg-orange-600' },
  tiktok:   { label: 'TikTok', abbr: 'TT', bg: 'bg-gray-900' },
}

/**
 * Mock campaign data (to be replaced with API calls).
 */
export const MOCK_CAMPAIGNS = [
  {
    id: 1,
    title: 'First-Mover Authority Play',
    description: 'Position your brand as the one that saw it coming. Data-driven thought leadership tying the Fed rate cut prediction to your product\'s value proposition.',
    recommended: true,
    signal: { name: 'Fed Expected to Cut Rates', probability: 78, color: 'blue' },
    channels: [
      { type: 'linkedin', format: 'Article', fit: 94 },
      { type: 'twitter', format: 'Thread', fit: 88 },
    ],
    confidence: 92,
  },
  {
    id: 2,
    title: 'Educational Explainer Series',
    description: 'Break down what the EU AI Act means for your audience. Three-part content series explaining compliance implications and how your product helps navigate them.',
    recommended: false,
    signal: { name: 'EU AI Act Enforcement Q2', probability: 62, color: 'teal' },
    channels: [
      { type: 'blog', format: 'Series', fit: 91 },
      { type: 'linkedin', format: 'Posts', fit: 85 },
      { type: 'email', format: 'Newsletter', fit: 82 },
    ],
    confidence: 85,
  },
  {
    id: 3,
    title: 'Market Momentum Hot Take',
    description: 'Fast-response reactive content on Bitcoin ETF momentum. Quick, opinionated takes that position your brand within the broader fintech conversation.',
    recommended: false,
    signal: { name: 'Bitcoin Spot ETF Record Inflows', probability: 91, color: 'blue' },
    channels: [
      { type: 'twitter', format: 'Thread', fit: 96 },
      { type: 'linkedin', format: 'Post', fit: 72 },
    ],
    confidence: 74,
  },
]

/**
 * Mock trending signals (for Trending page).
 */
export const MOCK_SIGNALS = [
  { id: 1, name: 'Fed Expected to Cut Rates in March', probability: 78, volume: '$4.2M', change: +12, category: 'Macro', timeframe: '48h' },
  { id: 2, name: 'EU AI Act Full Enforcement by Q2', probability: 62, volume: '$1.8M', change: +8, category: 'Regulation', timeframe: '7d' },
  { id: 3, name: 'Bitcoin Spot ETF Record Monthly Inflows', probability: 91, volume: '$6.1M', change: +3, category: 'Crypto', timeframe: '24h' },
  { id: 4, name: 'OpenAI GPT-5 Launch Before June', probability: 45, volume: '$2.3M', change: -5, category: 'AI', timeframe: '30d' },
  { id: 5, name: 'US TikTok Ban Takes Effect', probability: 34, volume: '$8.7M', change: +22, category: 'Social', timeframe: '14d' },
  { id: 6, name: 'Apple Vision Pro Price Cut by Q3', probability: 28, volume: '$920K', change: +15, category: 'Hardware', timeframe: '90d' },
  { id: 7, name: 'Stripe IPO in 2026', probability: 55, volume: '$3.4M', change: +2, category: 'Fintech', timeframe: '120d' },
  { id: 8, name: 'US Recession by Year End', probability: 22, volume: '$11.2M', change: -3, category: 'Macro', timeframe: '180d' },
]

/**
 * Mock past campaigns (for Campaigns page).
 */
export const MOCK_PAST_CAMPAIGNS = [
  {
    id: 101,
    title: 'AI Compliance Readiness Campaign',
    status: 'active',
    created: '2026-02-18',
    signal: 'EU AI Act Enforcement Q2',
    channels: ['linkedin', 'blog', 'email'],
    impressions: 12400,
    engagement: 3.8,
  },
  {
    id: 102,
    title: 'Rate Cut Opportunity Series',
    status: 'completed',
    created: '2026-02-10',
    signal: 'Fed Expected to Cut Rates',
    channels: ['twitter', 'linkedin'],
    impressions: 8900,
    engagement: 5.2,
  },
  {
    id: 103,
    title: 'Crypto Momentum Thread',
    status: 'draft',
    created: '2026-02-20',
    signal: 'Bitcoin Spot ETF Record Inflows',
    channels: ['twitter'],
    impressions: 0,
    engagement: 0,
  },
]

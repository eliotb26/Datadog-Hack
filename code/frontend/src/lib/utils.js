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

/**
 * Content type metadata for UI rendering.
 */
export const CONTENT_TYPE_CONFIG = {
  tweet_thread:       { label: 'Tweet Thread',       icon: '𝕏',  color: 'bg-gray-900',    textColor: 'text-gray-900',    bgLight: 'bg-gray-50' },
  linkedin_article:   { label: 'LinkedIn Article',   icon: 'in', color: 'bg-[#0A66C2]',   textColor: 'text-[#0A66C2]',   bgLight: 'bg-blue-50' },
  blog_post:          { label: 'Blog Post',          icon: 'B',  color: 'bg-emerald-600',  textColor: 'text-emerald-600',  bgLight: 'bg-emerald-50' },
  video_script:       { label: 'Video Script',       icon: '▶',  color: 'bg-red-600',      textColor: 'text-red-600',      bgLight: 'bg-red-50' },
  infographic:        { label: 'Infographic',        icon: '◎',  color: 'bg-violet-600',   textColor: 'text-violet-600',   bgLight: 'bg-violet-50' },
  newsletter:         { label: 'Newsletter',         icon: '@',  color: 'bg-teal-600',     textColor: 'text-teal-600',     bgLight: 'bg-teal-50' },
  instagram_carousel: { label: 'IG Carousel',        icon: 'IG', color: 'bg-pink-500',     textColor: 'text-pink-500',     bgLight: 'bg-pink-50' },
}

/**
 * Mock content strategies (Agent 6 output).
 */
export const MOCK_CONTENT_STRATEGIES = [
  {
    id: 'cs-001',
    campaignId: 101,
    campaignTitle: 'AI Compliance Readiness Campaign',
    contentType: 'linkedin_article',
    reasoning: 'LinkedIn article is the ideal format for reaching enterprise decision-makers with in-depth compliance analysis. The professional audience expects long-form thought leadership on regulatory topics.',
    targetLength: '1200-word article',
    toneDirection: 'Authoritative, reassuring, data-backed',
    structureOutline: ['Hook: The compliance clock is ticking', 'What the EU AI Act means for your business', '3 steps to prepare today', 'How our platform simplifies compliance', 'CTA: Book a compliance audit'],
    priorityScore: 0.92,
    visualNeeded: false,
  },
  {
    id: 'cs-002',
    campaignId: 101,
    campaignTitle: 'AI Compliance Readiness Campaign',
    contentType: 'tweet_thread',
    reasoning: 'A tweet thread can distil the key compliance takeaways into shareable bites. Great for amplifying the LinkedIn piece and driving traffic.',
    targetLength: '6-tweet thread',
    toneDirection: 'Concise, punchy, slightly urgent',
    structureOutline: ['Hook: surprising stat about AI regulation', 'What changed this quarter', 'The 3 things most companies miss', 'What smart teams are doing differently', 'Our take + data point', 'CTA: link to full article'],
    priorityScore: 0.85,
    visualNeeded: false,
  },
  {
    id: 'cs-003',
    campaignId: 102,
    campaignTitle: 'Rate Cut Opportunity Series',
    contentType: 'newsletter',
    reasoning: 'A newsletter lets us go deeper on the financial analysis while maintaining a personal, conversational tone with our engaged subscriber base.',
    targetLength: '800-word newsletter',
    toneDirection: 'Conversational, insightful, actionable',
    structureOutline: ['Opening: Why this rate cut matters to you', 'Market context in 60 seconds', 'What our data shows', 'Three actionable takeaways', 'Sign-off with upcoming preview'],
    priorityScore: 0.88,
    visualNeeded: false,
  },
]

/**
 * Mock content pieces (Agent 7 output).
 */
export const MOCK_CONTENT_PIECES = [
  {
    id: 'cp-001',
    strategyId: 'cs-001',
    campaignId: 101,
    contentType: 'linkedin_article',
    title: 'The EU AI Act Is Here — Is Your Company Ready?',
    body: `The EU AI Act officially enters enforcement in Q2 2026, and prediction markets are pricing it at 62% certainty. For companies building or deploying AI systems, the window to prepare is closing fast.\n\n## What the EU AI Act Means for Your Business\n\nThe regulation classifies AI systems into risk tiers — from minimal to unacceptable. If your product uses AI for hiring, credit scoring, or content moderation, you're likely in the "high-risk" category. That means mandatory conformity assessments, ongoing monitoring, and detailed documentation.\n\n## 3 Steps to Prepare Today\n\n**1. Audit your AI inventory.** Map every AI system in your stack. You can't comply with what you can't see.\n\n**2. Classify your risk tier.** Use the Act's Annex III criteria to determine where each system falls.\n\n**3. Start documentation now.** The biggest compliance bottleneck isn't technical — it's documentation. Start building your technical file today.\n\n## How We Can Help\n\nOur platform automatically maps your AI systems, classifies risk tiers, and generates compliance documentation — turning months of manual work into days.\n\nThe companies that act now won't just avoid fines. They'll earn trust. And in the AI era, trust is the ultimate competitive advantage.\n\n---\n*Ready to get ahead of the regulation? Book a 15-minute compliance audit with our team.*`,
    summary: 'Deep-dive on EU AI Act compliance readiness for enterprise audiences.',
    wordCount: 1180,
    qualityScore: 0.91,
    brandAlignment: 0.88,
    status: 'draft',
    createdAt: '2026-02-20T10:30:00Z',
  },
  {
    id: 'cp-002',
    strategyId: 'cs-002',
    campaignId: 101,
    contentType: 'tweet_thread',
    title: 'EU AI Act Compliance Thread',
    body: JSON.stringify([
      '🚨 The EU AI Act enforcement starts Q2 2026. Prediction markets: 62% certainty.\n\nMost companies aren\'t ready. Here\'s what you need to know (and do) right now:\n\n🧵 [1/6]',
      'The Act classifies AI into risk tiers. If you use AI for hiring, credit, or content moderation — you\'re "high-risk."\n\nThat means: mandatory assessments, ongoing monitoring, and detailed docs.\n\nMost teams underestimate the documentation burden. [2/6]',
      'The 3 things most companies miss:\n\n1. Shadow AI — models in production nobody tracks\n2. Risk classification — assuming "low-risk" without checking Annex III\n3. Documentation debt — starting too late on technical files\n\n[3/6]',
      'What smart teams are doing RIGHT NOW:\n\n✅ Full AI system inventory\n✅ Risk tier classification\n✅ Compliance documentation pipeline\n✅ Vendor assessment for third-party models\n\nThe playbook isn\'t complex. Starting early is the advantage. [4/6]',
      'Our data shows companies that start compliance prep 6+ months before enforcement save 40% on audit costs and reduce remediation time by 3x.\n\nThe ROI on early action is real. [5/6]',
      'Don\'t wait for enforcement to force your hand.\n\nWe built a platform that maps your AI systems, classifies risk, and generates compliance docs automatically.\n\n→ Book a free 15-min compliance audit: [link]\n\n[6/6]'
    ]),
    summary: '6-tweet thread breaking down EU AI Act compliance essentials.',
    wordCount: 320,
    qualityScore: 0.87,
    brandAlignment: 0.85,
    status: 'draft',
    createdAt: '2026-02-20T10:45:00Z',
  },
  {
    id: 'cp-003',
    strategyId: 'cs-003',
    campaignId: 102,
    contentType: 'newsletter',
    title: 'The Rate Cut Is Coming — Here\'s What It Means for You',
    body: `Hey there,\n\nBig news from the prediction markets this week: the probability of a Fed rate cut in March just hit 78%, up 12 points in 48 hours. This isn't noise — it's a signal.\n\nLet me break down what this means and what you should do about it.\n\n## Market Context in 60 Seconds\n\nAfter months of hawkish rhetoric, the data is shifting. Core inflation is trending down, job growth is moderating, and the bond market is already pricing in cuts. Polymarket volume on this question alone: $4.2 million.\n\n## What Our Data Shows\n\nWe've tracked the correlation between rate-cut signals and fintech engagement metrics across 200+ campaigns. Here's what we found:\n\n- **Rate-sensitive content** sees 2.3× higher engagement during high-probability cut windows\n- **Timing matters**: the 48-hour window after probability crosses 70% is the engagement sweet spot\n- **Audience response**: B2B finance audiences are 40% more likely to engage with forward-looking analysis\n\n## Three Actionable Takeaways\n\n1. **Publish rate-sensitive content NOW** — you're in the engagement sweet spot\n2. **Lead with data** — your audience wants analysis, not opinion\n3. **Connect it to your product** — how does a rate cut help your customers?\n\n## Coming Next Week\n\nWe're watching the Bitcoin ETF inflow data closely — the signal is building and we'll have a full analysis ready for you.\n\nStay ahead of the curve,\n*The SIGNAL Team*`,
    summary: 'Weekly newsletter on Fed rate cut probability and actionable fintech content strategy.',
    wordCount: 820,
    qualityScore: 0.89,
    brandAlignment: 0.92,
    status: 'draft',
    createdAt: '2026-02-19T14:00:00Z',
  },
]

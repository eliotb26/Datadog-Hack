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
    title: '"The Winning Side" Sports Activation',
    description: "Coca-Cola pre-produces 'We called it' victory content keyed to tonight's high-confidence matchups — Spurs (93%), Man City (80%), Atlético (98%). Drop polished creative within seconds of the final whistle. Prediction markets give us the edge to be first every time.",
    recommended: true,
    signal: { name: 'NBA Spurs Win + EPL Man City Win + La Liga Atlético Win', probability: 93, color: 'blue' },
    channels: [
      { type: 'instagram', format: 'Story', fit: 97 },
      { type: 'tiktok', format: 'Reel', fit: 94 },
      { type: 'twitter', format: 'Post', fit: 89 },
    ],
    confidence: 94,
  },
  {
    id: 2,
    title: '"One Sure Thing" — Shutdown Relief',
    description: "When DC is at 97% odds of a 14-day shutdown, Coca-Cola steps in as the one daily certainty. Wry, culturally self-aware creative: 'We can't fix Washington. We can fix your afternoon.' Inserts the brand into the moment without taking sides.",
    recommended: false,
    signal: { name: 'DHS Shutdown Lasts 14+ Days', probability: 97, color: 'teal' },
    channels: [
      { type: 'twitter', format: 'Thread', fit: 92 },
      { type: 'instagram', format: 'Feed Post', fit: 85 },
      { type: 'tiktok', format: 'Stitch', fit: 81 },
    ],
    confidence: 87,
  },
  {
    id: 3,
    title: '"AI Can\'t Replace This" Cultural Moment',
    description: "As Polymarket puts Anthropic at 92% odds of best AI model end of February, Coca-Cola owns the counter-narrative: the one thing no model can replicate — a real Coke in your hand. Ironic creative: 'Anthropic may have the best model. We have the best bottle.'",
    recommended: false,
    signal: { name: 'Anthropic Best AI Model — End of February', probability: 92, color: 'blue' },
    channels: [
      { type: 'twitter', format: 'Thread', fit: 96 },
      { type: 'instagram', format: 'Reel', fit: 88 },
      { type: 'reddit', format: 'Post', fit: 79 },
    ],
    confidence: 81,
  },
]

/**
 * Mock trending signals (for Trending page).
 */
export const MOCK_SIGNALS = [
  { id: 1, name: 'NBA: San Antonio Spurs Win vs Sacramento Kings', probability: 93, volume: '$2.0M', change: +5, category: 'Sports', timeframe: 'Tonight 8PM' },
  { id: 2, name: 'EPL: Manchester City Win vs Newcastle United', probability: 80, volume: '$7.0M', change: +8, category: 'Sports', timeframe: 'Live — 69 min' },
  { id: 3, name: 'La Liga: Club Atlético de Madrid Win vs RCD Espanyol', probability: 98, volume: '$8.0M', change: +3, category: 'Sports', timeframe: 'Live — 67 min' },
  { id: 4, name: 'DHS Shutdown Lasts 14+ Days', probability: 97, volume: '$769K', change: +22, category: 'Politics', timeframe: '14d' },
  { id: 5, name: 'S&P 500 (SPX) Opens Up on February 23', probability: 51, volume: '$67K', change: +2, category: 'Macro', timeframe: '24h' },
  { id: 6, name: 'Will Trump Visit China by March 31, 2026?', probability: 79, volume: '$2.0M', change: +14, category: 'Politics', timeframe: '38d' },
  { id: 7, name: 'Anthropic Has Best AI Model — End of February', probability: 92, volume: '$18M', change: +6, category: 'AI', timeframe: '7d' },
  { id: 8, name: 'Will Court Force Trump to Refund Tariffs?', probability: 18, volume: '$116K', change: -4, category: 'Politics', timeframe: '30d' },
  { id: 9, name: 'NBA: Phoenix Suns Win vs Orlando Magic', probability: 60, volume: '$2.0M', change: +1, category: 'Sports', timeframe: 'Tonight 5PM' },
  { id: 10, name: 'Serie A: SS Lazio Win vs Cagliari Calcio', probability: 28, volume: '$4.0M', change: -2, category: 'Sports', timeframe: 'Live — 88 min' },
  { id: 11, name: 'Will Iranian Regime Fall Before 2027?', probability: 39, volume: '$5.0M', change: +9, category: 'Geopolitics', timeframe: '1yr' },
  { id: 12, name: 'Clarity Act Signed Into Law in 2026', probability: 72, volume: '$100K', change: +11, category: 'Crypto', timeframe: '90d' },
]

/**
 * Mock generated content per campaign (keyed by campaign id).
 */
export const MOCK_CAMPAIGN_CONTENT = {
  1: {
    headline: 'Real Magic at the Final Whistle',
    summary: 'Pre-produced victory content ready to publish the moment the game ends. Prediction markets gave us the edge — 93% Spurs, 80% Man City, 98% Atlético. We go first, every time.',
    pieces: [
      {
        channel: 'instagram',
        format: 'Story',
        caption: "They didn't even see it coming. We did. 🏆🥤\n\nSpurs. Man City. Atlético.\n\nSome things are just inevitable.\n\n#RealMagic #CocaCola #WinningMoments",
        imagePrompt: 'Coca-Cola bottle exploding with confetti and stadium lights, vibrant red and white, photorealistic celebration',
        image: '/coca-cola-sports.png',
      },
      {
        channel: 'tiktok',
        format: 'Reel',
        caption: "POV: You called all 3 wins before the whistle 🎯🥤 The Real Thing always knows. #CocaCola #RealMagic #SportsNight #Spurs #ManCity #Atletico",
        imagePrompt: 'Coca-Cola can with winning scoreboard reflection, cinematic lighting, stadium atmosphere',
      },
      {
        channel: 'twitter',
        format: 'Post',
        caption: "Spurs ✅ Man City ✅ Atlético ✅\n\nPrediction markets had it. We had the Coke ready.\n\nThe Real Thing doesn't wait for the final score. 🥤\n\n#RealMagic",
        imagePrompt: 'Coca-Cola bottle against a triple-split scoreboard showing three wins, bold red palette',
      },
    ],
  },
  2: {
    headline: 'One Sure Thing',
    summary: "When DC is gridlocked at 97% odds of a 14-day shutdown, Coca-Cola steps in as the one daily certainty people can count on. Wry, warm, and culturally aware — without taking sides.",
    pieces: [
      {
        channel: 'twitter',
        format: 'Thread',
        caption: "We can't fix Washington.\n\nWe can fix your afternoon. 🥤\n\nDay 14 of the shutdown. Coca-Cola: still reliable, still cold, still delicious.\n\n#OneSureThing #CocaCola",
        imagePrompt: 'Coca-Cola can sitting on a Capitol Hill steps with warm afternoon light, editorial photography style',
      },
      {
        channel: 'instagram',
        format: 'Feed Post',
        caption: "Governments come and go. The feeling of an ice-cold Coke? Permanent. 🥤❤️\n\n#OneSureThing #CocaCola #RealMagic",
        imagePrompt: 'Close-up of a Coca-Cola can with condensation, soft warm background, minimalist product shot',
      },
      {
        channel: 'tiktok',
        format: 'Stitch',
        caption: "14 days. Still no deal. But my Coke is still cold ☕🥤 #shutdown #cocacola #OneSureThing #fyp",
        imagePrompt: 'Person opening an ice-cold Coca-Cola in front of a blurred news broadcast, candid lifestyle',
      },
    ],
  },
  3: {
    headline: "AI Can't Replace This",
    summary: "As Polymarket puts Anthropic at 92% for best AI model, Coca-Cola owns the counter-narrative: the one thing no model can replicate — a real Coke in your hand. Ironic, culturally sharp, shareable.",
    pieces: [
      {
        channel: 'twitter',
        format: 'Thread',
        caption: "Anthropic may have the best model.\n\nWe have the best bottle. 🥤\n\nSome things can't be tokenised. Some feelings can't be fine-tuned. The Real Thing is still the real thing.\n\n#CocaCola #AICanTReplaceThis",
        imagePrompt: 'Coca-Cola bottle next to a glowing AI chip/circuit board, contrasting warm red vs cool blue tech aesthetic',
      },
      {
        channel: 'instagram',
        format: 'Reel',
        caption: "Claude can write a poem. GPT-4 can write code.\n\nNeither can replicate THIS. 🥤✨\n\n#CocaCola #RealMagic #AICanTReplaceThis",
        imagePrompt: 'Split frame: holographic AI interface on left, classic Coca-Cola bottle on right, bold contrast',
      },
      {
        channel: 'reddit',
        format: 'Post',
        caption: "[Coca-Cola] We've been following the AI model race closely. Anthropic's at 92% on Polymarket. Impressive. But no LLM has cracked the taste of an ice-cold Coke yet. We'll be watching. 🥤",
        imagePrompt: 'Minimalist Coca-Cola logo on dark background with subtle AI grid pattern, r/technology aesthetic',
      },
    ],
  },
}

/**
 * Mock past campaigns (for Campaigns page).
 */
export const MOCK_PAST_CAMPAIGNS = [
  {
    id: 101,
    title: '"The Winning Side" Sports Activation',
    status: 'active',
    created: '2026-02-21',
    signal: 'NBA Spurs Win + EPL Man City Win',
    channels: ['instagram', 'tiktok', 'twitter'],
    impressions: 284000,
    engagement: 6.4,
  },
  {
    id: 102,
    title: '"One Sure Thing" — Shutdown Relief',
    status: 'completed',
    created: '2026-02-15',
    signal: 'DHS Shutdown Lasts 14+ Days',
    channels: ['twitter', 'instagram'],
    impressions: 193500,
    engagement: 8.1,
  },
  {
    id: 103,
    title: '"AI Can\'t Replace This" Cultural Moment',
    status: 'draft',
    created: '2026-02-21',
    signal: 'Anthropic Best AI Model End of February',
    channels: ['twitter', 'instagram', 'reddit'],
    impressions: 0,
    engagement: 0,
  },
]

import { useState, useEffect, useCallback } from 'react'
import { ChevronDown, ChevronRight, Copy, Check, Eye, Sparkles, Loader2, RefreshCw, Image as ImageIcon, Film } from 'lucide-react'
import { cn, CONTENT_TYPE_CONFIG } from '@/lib/utils'
import { apiFetch, submitAndPoll, API_BASE } from '@/lib/api'

const STATUS_STYLES = {
  draft:     'bg-amber-50 text-amber-600',
  review:    'bg-blue-50 text-blue-600',
  approved:  'bg-emerald-50 text-emerald-600',
  published: 'bg-gray-100 text-gray-500',
}

function ContentTypeBadge({ type }) {
  const config = CONTENT_TYPE_CONFIG[type]
  if (!config) return null
  return (
    <span className={cn('inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-semibold', config.bgLight, config.textColor)}>
      <span className={cn('w-5 h-5 rounded grid place-items-center text-[10px] font-bold text-white', config.color)}>
        {config.icon}
      </span>
      {config.label}
    </span>
  )
}

function ContentPieceView({ piece }) {
  const [showFull, setShowFull] = useState(false)
  const [copied, setCopied] = useState(false)

  const isThread = piece.content_type === 'tweet_thread'
  let tweets = []
  if (isThread) {
    try { tweets = JSON.parse(piece.body) } catch { tweets = [piece.body] }
  }

  const handleCopy = () => {
    const text = isThread ? tweets.join('\n\n---\n\n') : piece.body
    navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="border-t border-gray-100">
      <div className="flex items-center justify-between px-6 py-3 bg-white">
        <div className="flex items-center gap-3">
          <ContentTypeBadge type={piece.content_type} />
          <span className="text-sm font-semibold text-gray-900">{piece.title}</span>
          <span className={cn('px-2 py-0.5 rounded text-[10px] font-semibold capitalize', STATUS_STYLES[piece.status] || STATUS_STYLES.draft)}>
            {piece.status}
          </span>
          {piece.visual_asset_url && (
            <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-indigo-50 text-indigo-600 text-[10px] font-bold uppercase tracking-wider">
              {piece.visual_asset_url.includes('video') ? <Film size={10} /> : <ImageIcon size={10} />}
              Visual
            </span>
          )}
        </div>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-3 text-xs text-gray-400">
            <span>{piece.word_count} words</span>
            <span>Quality: <span className="font-semibold text-gray-700">{Math.round((piece.quality_score || 0) * 100)}%</span></span>
            <span>Brand: <span className="font-semibold text-gray-700">{Math.round((piece.brand_alignment || 0) * 100)}%</span></span>
          </div>
          <button
            onClick={handleCopy}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-gray-200 text-xs font-semibold text-gray-500 hover:bg-gray-50 transition-fast"
          >
            {copied ? <Check size={14} className="text-emerald-500" /> : <Copy size={14} />}
            {copied ? 'Copied' : 'Copy'}
          </button>
          <button
            onClick={() => setShowFull(!showFull)}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-gray-200 text-xs font-semibold text-gray-500 hover:bg-gray-50 transition-fast"
          >
            <Eye size={14} />
            {showFull ? 'Collapse' : 'Preview'}
          </button>
        </div>
      </div>

      <div className="px-6 pb-5">
        {piece.visual_asset_url && showFull && (
          <div className="mb-4 rounded-xl overflow-hidden border border-gray-100 bg-gray-50 aspect-video flex items-center justify-center relative group">
            {piece.visual_asset_url.includes('video') ? (
              <video 
                src={`${API_BASE}${piece.visual_asset_url}`} 
                controls 
                className="w-full h-full object-cover"
              />
            ) : (
              <img 
                src={`${API_BASE}${piece.visual_asset_url}`} 
                alt={piece.title}
                className="w-full h-full object-cover"
              />
            )}
            <div className="absolute top-3 right-3 px-2 py-1 rounded-md bg-black/50 text-white text-[10px] font-bold backdrop-blur-sm opacity-0 group-hover:opacity-100 transition-opacity">
              AI Generated
            </div>
          </div>
        )}
        {isThread ? (
          <div className="flex flex-col gap-2">
            {(showFull ? tweets : tweets.slice(0, 2)).map((tweet, i) => (
              <div key={i} className="flex gap-3">
                <div className="w-8 h-8 rounded-full bg-gray-900 grid place-items-center text-white text-[10px] font-bold shrink-0 mt-0.5">𝕏</div>
                <div className="flex-1 bg-gray-50 rounded-xl px-4 py-3 text-sm text-gray-700 leading-relaxed whitespace-pre-wrap border border-gray-100">
                  {tweet}
                </div>
              </div>
            ))}
            {!showFull && tweets.length > 2 && (
              <button onClick={() => setShowFull(true)} className="text-xs text-brand font-semibold hover:underline ml-11">
                Show {tweets.length - 2} more tweets...
              </button>
            )}
          </div>
        ) : (
          <div className={cn(
            'bg-gray-50 rounded-xl px-5 py-4 text-sm text-gray-700 leading-relaxed border border-gray-100 prose prose-sm max-w-none',
            !showFull && 'max-h-[180px] overflow-hidden relative'
          )}>
            <div className="whitespace-pre-wrap">{piece.body}</div>
            {!showFull && (
              <div className="absolute bottom-0 left-0 right-0 h-16 bg-gradient-to-t from-gray-50 to-transparent flex items-end justify-center pb-2">
                <button onClick={() => setShowFull(true)} className="text-xs text-brand font-semibold hover:underline bg-gray-50 px-3 py-1 rounded">
                  Show full content...
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

function StrategyCard({ strategy, isExpanded, onToggle, pieces, onGeneratePiece, generatingPiece }) {
  const config = CONTENT_TYPE_CONFIG[strategy.content_type]

  return (
    <div className="bg-white border border-gray-200 rounded-xl overflow-hidden fade-in">
      {/* Header */}
      <button
        onClick={onToggle}
        className="w-full flex items-center gap-4 px-6 py-4 hover:bg-gray-50/50 transition-fast text-left"
      >
        <div className={cn('w-10 h-10 rounded-xl grid place-items-center text-sm font-bold text-white shrink-0', config?.color || 'bg-gray-500')}>
          {config?.icon || '?'}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-0.5">
            <span className="text-sm font-bold text-gray-900">{config?.label || strategy.content_type}</span>
            <span className="text-[11px] font-semibold text-gray-400">for campaign {strategy.campaign_id?.slice(0, 8)}…</span>
          </div>
          <p className="text-xs text-gray-500 truncate max-w-[500px]">{strategy.reasoning}</p>
        </div>
        <div className="flex items-center gap-3 shrink-0">
          <div className="text-right">
            <div className="text-xs text-gray-400">Priority</div>
            <div className="text-sm font-bold text-gray-900">{Math.round((strategy.priority_score || 0) * 100)}%</div>
          </div>
          <div className="text-right">
            <div className="text-xs text-gray-400">Length</div>
            <div className="text-xs font-semibold text-gray-600">{strategy.target_length}</div>
          </div>
          {isExpanded ? <ChevronDown size={18} className="text-gray-400" /> : <ChevronRight size={18} className="text-gray-400" />}
        </div>
      </button>

      {/* Expanded */}
      {isExpanded && (
        <div className="border-t border-gray-100">
          {/* Strategy outline */}
          <div className="px-6 py-4 bg-gray-50/50">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <Sparkles size={14} className="text-brand" />
                <span className="text-[11px] font-bold uppercase tracking-wider text-gray-400">Content Outline</span>
                <span className="text-[10px] text-gray-400">— Agent 6 strategy</span>
              </div>
              {pieces.length === 0 && (
                <button
                  onClick={() => onGeneratePiece(strategy.id)}
                  disabled={generatingPiece === strategy.id}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-violet-600 text-white text-xs font-semibold hover:bg-violet-700 disabled:opacity-50 transition-fast"
                >
                  {generatingPiece === strategy.id
                    ? <Loader2 size={12} className="animate-spin" />
                    : <Sparkles size={12} />}
                  {generatingPiece === strategy.id ? 'Generating…' : 'Generate Content'}
                </button>
              )}
            </div>
            <div className="flex flex-wrap gap-2">
              {(strategy.structure_outline || []).map((beat, i) => (
                <span key={i} className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-white border border-gray-200 text-xs text-gray-600">
                  <span className="w-4 h-4 rounded bg-brand-50 text-brand grid place-items-center text-[10px] font-bold shrink-0">{i + 1}</span>
                  {beat}
                </span>
              ))}
            </div>
            <div className="mt-2 text-[11px] text-gray-400">
              Tone: <span className="font-medium text-gray-600">{strategy.tone_direction}</span>
            </div>
          </div>

          {/* Generated content pieces */}
          {pieces.length > 0 ? (
            pieces.map(piece => (
              <ContentPieceView key={piece.id} piece={piece} />
            ))
          ) : (
            <div className="px-6 py-8 text-center">
              <Sparkles size={24} className="mx-auto text-gray-300 mb-2" />
              <p className="text-sm text-gray-400">
                {generatingPiece === strategy.id
                  ? 'Agent 7 is writing your content…'
                  : 'Content not yet generated. Click "Generate Content" to run Agent 7.'}
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default function ContentStudio() {
  const [expandedStrategy, setExpandedStrategy] = useState(null)
  const [typeFilter, setTypeFilter] = useState('all')
  const [strategies, setStrategies] = useState([])
  const [pieces, setPieces] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [generatingPiece, setGeneratingPiece] = useState(null) // strategy_id being generated

  const fetchData = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [strats, pcs] = await Promise.all([
        apiFetch('/api/content/strategies'),
        apiFetch('/api/content/pieces'),
      ])
      setStrategies(strats)
      setPieces(pcs)
      if (strats.length > 0 && !expandedStrategy) {
        setExpandedStrategy(strats[0].id)
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  const handleGeneratePiece = async (strategyId) => {
    setGeneratingPiece(strategyId)
    try {
      const result = await submitAndPoll(
        '/api/content/pieces/generate',
        { strategy_id: strategyId },
        { intervalMs: 3000, timeoutMs: 120_000 }
      )
      // Merge new pieces into state
      const newPieces = result?.pieces || []
      setPieces(prev => [...prev.filter(p => p.strategy_id !== strategyId), ...newPieces])
    } catch (err) {
      setError(err.message)
    } finally {
      setGeneratingPiece(null)
    }
  }

  const activeTypes = [...new Set(strategies.map(s => s.content_type))]

  const filteredStrategies = typeFilter === 'all'
    ? strategies
    : strategies.filter(s => s.content_type === typeFilter)

  return (
    <div className="flex-1 overflow-y-auto custom-scrollbar">
      {/* Header */}
      <div className="px-8 pt-8 pb-6">
        <div className="flex items-center justify-between mb-1">
          <div>
            <h1 className="text-2xl font-extrabold text-gray-900 tracking-tight">Content Studio</h1>
            <p className="text-sm text-gray-500 mt-1">AI-generated content from your campaign strategies. Review, edit, and publish.</p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={fetchData}
              disabled={loading}
              className="inline-flex items-center gap-1.5 px-3 py-[5px] rounded-full text-xs font-semibold border border-gray-200 text-gray-500 hover:bg-gray-50 disabled:opacity-50 transition-fast"
            >
              {loading ? <Loader2 size={12} className="animate-spin" /> : <RefreshCw size={12} />}
              Refresh
            </button>
            <span className="inline-flex items-center gap-1.5 px-3 py-[5px] rounded-full text-xs font-semibold bg-violet-50 text-violet-600">
              <Sparkles size={12} />
              {pieces.length} pieces generated
            </span>
          </div>
        </div>

        {/* Pipeline explanation */}
        <div className="mt-4 flex items-center gap-2 px-4 py-3 bg-brand-50 rounded-xl border border-brand/10">
          <div className="flex items-center gap-1.5 text-xs">
            <span className="px-2 py-0.5 rounded bg-brand text-white font-bold">Agent 6</span>
            <span className="text-gray-500">Strategy decides the format</span>
            <span className="text-gray-300 mx-1">→</span>
            <span className="px-2 py-0.5 rounded bg-violet-600 text-white font-bold">Agent 7</span>
            <span className="text-gray-500">Production generates full content</span>
            <span className="text-gray-300 mx-1">→</span>
            <span className="px-2 py-0.5 rounded bg-emerald-600 text-white font-bold">Review</span>
            <span className="text-gray-500">You approve &amp; publish</span>
          </div>
        </div>

        {error && (
          <p className="mt-4 text-sm text-red-600 bg-red-50 px-4 py-2 rounded-lg">{error}</p>
        )}

        {/* Type filters */}
        {activeTypes.length > 0 && (
          <div className="flex items-center gap-2 mt-5">
            <div className="flex gap-1 p-1 bg-surface-alt rounded-lg">
              <button
                onClick={() => setTypeFilter('all')}
                className={cn(
                  'px-3 py-1.5 rounded-md text-xs font-semibold transition-fast',
                  typeFilter === 'all' ? 'bg-white text-gray-900 shadow-card' : 'text-gray-500 hover:text-gray-700'
                )}
              >
                All Types
              </button>
              {activeTypes.map(t => {
                const config = CONTENT_TYPE_CONFIG[t]
                return (
                  <button
                    key={t}
                    onClick={() => setTypeFilter(t)}
                    className={cn(
                      'px-3 py-1.5 rounded-md text-xs font-semibold transition-fast inline-flex items-center gap-1.5',
                      typeFilter === t ? 'bg-white text-gray-900 shadow-card' : 'text-gray-500 hover:text-gray-700'
                    )}
                  >
                    <span className={cn('w-4 h-4 rounded grid place-items-center text-[9px] font-bold text-white', config?.color || 'bg-gray-400')}>
                      {config?.icon || '?'}
                    </span>
                    {config?.label || t}
                  </button>
                )
              })}
            </div>
          </div>
        )}
      </div>

      {/* Strategy list with nested content */}
      <div className="px-8 pb-8">
        {loading ? (
          <div className="flex items-center justify-center py-24 text-gray-400">
            <Loader2 size={24} className="animate-spin mr-3" />
            <span className="text-sm">Loading content studio…</span>
          </div>
        ) : filteredStrategies.length === 0 ? (
          <div className="text-center py-16">
            {strategies.length === 0 ? (
              <>
                <Sparkles size={32} className="mx-auto text-gray-300 mb-3" />
                <p className="text-sm text-gray-400 mb-2">No content strategies yet.</p>
                <p className="text-xs text-gray-300">Generate campaigns first, then approve one to trigger Agent 6 strategy generation.</p>
              </>
            ) : (
              <p className="text-sm text-gray-400">No content strategies match this filter.</p>
            )}
          </div>
        ) : (
          <div className="flex flex-col gap-4">
            {filteredStrategies.map(strategy => {
              const stratPieces = pieces.filter(p => p.strategy_id === strategy.id)
              return (
                <StrategyCard
                  key={strategy.id}
                  strategy={strategy}
                  isExpanded={expandedStrategy === strategy.id}
                  onToggle={() => setExpandedStrategy(expandedStrategy === strategy.id ? null : strategy.id)}
                  pieces={stratPieces}
                  onGeneratePiece={handleGeneratePiece}
                  generatingPiece={generatingPiece}
                />
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}

import { useState, useRef, useCallback, useEffect } from 'react'
import { Send, RotateCcw, Plus, Loader2, Globe, ChevronDown, ChevronRight } from 'lucide-react'
import { cn, detectCampaignInfo, countCompleted } from '@/lib/utils'
import { submitAndPoll, apiFetch } from '@/lib/api'
import CampaignCard from '@/components/CampaignCard'
import ChecklistItem from '@/components/ChecklistItem'

const TAG_SUGGESTIONS = [
  { label: 'Company type', text: 'We are a fintech SaaS company' },
  { label: 'Audience', text: 'targeting B2B enterprise customers' },
  { label: 'Campaign goal', text: 'our goal is brand awareness and thought leadership' },
  { label: 'Channels', text: 'we want to post on LinkedIn and Twitter' },
]

function normalizeWebsiteUrl(val) {
  const s = (val || '').trim()
  if (!s) return null
  if (/^https?:\/\//i.test(s)) return s
  return `https://${s}`
}

function deriveCompanyNameFromWebsite(url) {
  try {
    const host = new URL(url).hostname.replace(/^www\./i, '')
    const root = host.split('.')[0] || 'Company'
    return root.charAt(0).toUpperCase() + root.slice(1)
  } catch {
    return 'Company'
  }
}

function isValidUrl(val) {
  const s = (val || '').trim()
  if (!s) return false
  if (/^https?:\/\/.+\..+/.test(s)) return true
  if (/^[a-z0-9][a-z0-9.-]*\.[a-z]{2,}(\/.*)?$/i.test(s)) return true
  return false
}

function normalizeCampaign(c, signalMap = {}) {
  const signal = signalMap[c.trend_signal_id] || {}
  return {
    id: c.id,
    title: c.headline,
    description: c.body_copy,
    recommended: (c.confidence_score || 0) >= 0.85,
    signal: {
      name: signal.title || c.trend_signal_id || 'Trend signal',
      probability: Math.round((signal.probability || 0) * 100),
      color: 'blue',
    },
    channels: [
      {
        type: c.channel_recommendation?.toLowerCase() || 'linkedin',
        format: 'Post',
        fit: Math.round((c.confidence_score || 0) * 100),
      },
    ],
    confidence: Math.round((c.confidence_score || 0) * 100),
    raw: c,
  }
}

function parseChannelScores(value) {
  if (!value) return []
  if (Array.isArray(value)) return value
  if (typeof value === 'string') {
    try {
      const parsed = JSON.parse(value)
      return Array.isArray(parsed) ? parsed : []
    } catch {
      return []
    }
  }
  return []
}

function normalizeDistributionPlans(plans = []) {
  return plans.map((plan) => ({
    ...plan,
    channel_scores: parseChannelScores(plan.channel_scores),
  }))
}

function buildAgentTextOutputs(agentOutputs) {
  const signalsText = (agentOutputs.signals || []).map((sig, idx) => {
    const prob = Math.round((sig.probability || 0) * 100)
    const momentum = (sig.probability_momentum || 0).toFixed(2)
    const volume = `$${(sig.volume || 0).toLocaleString()}`
    return [
      `${idx + 1}. ${sig.title || 'Untitled signal'}`,
      `Category: ${sig.category || 'general'} | Probability: ${prob}% | Momentum: ${momentum} | Volume: ${volume}`,
    ].join('\n')
  }).join('\n\n')

  const campaignsText = (agentOutputs.campaigns || []).map((c, idx) => {
    const confidence = Math.round((c.confidence_score || 0) * 100)
    return [
      `${idx + 1}. ${c.headline || 'Untitled concept'}`,
      `Channel: ${c.channel_recommendation || 'N/A'} | Confidence: ${confidence}% | Safety: ${c.safety_passed ? 'pass' : 'blocked'}`,
      c.body_copy || 'No body copy generated.',
      c.channel_reasoning ? `Channel reasoning: ${c.channel_reasoning}` : null,
      c.visual_direction ? `Visual direction: ${c.visual_direction}` : null,
    ].filter(Boolean).join('\n')
  }).join('\n\n')

  const distributionText = (agentOutputs.distributionPlans || []).map((plan, idx) => {
    const confidence = Math.round((plan.confidence || 0) * 100)
    const channelScores = (plan.channel_scores || [])
      .map((score) => `${score.channel}: ${Math.round((score.fit_score || 0) * 100)}% fit`)
      .join(' | ')

    return [
      `${idx + 1}. Recommended channel: ${plan.recommended_channel || 'N/A'} (${confidence}% confidence)`,
      `Posting time: ${plan.posting_time || 'N/A'}`,
      plan.reasoning ? `Reasoning: ${plan.reasoning}` : null,
      plan.format_adaptation ? `Format adaptation: ${plan.format_adaptation}` : null,
      channelScores ? `Channel scores: ${channelScores}` : null,
    ].filter(Boolean).join('\n')
  }).join('\n\n')

  return {
    signalsText: signalsText || 'No signal text generated.',
    campaignsText: campaignsText || 'No campaign text generated.',
    distributionText: distributionText || 'No distribution text generated.',
  }
}

function AgentSection({ title, count, expanded, onToggle, children }) {
  return (
    <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
      <button
        onClick={onToggle}
        className="w-full px-4 py-3 flex items-center justify-between text-left hover:bg-gray-50 transition-fast"
      >
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-gray-900">{title}</span>
          <span className="text-[11px] px-2 py-0.5 rounded-full bg-gray-100 text-gray-600 font-semibold">{count}</span>
        </div>
        {expanded ? <ChevronDown size={16} className="text-gray-400" /> : <ChevronRight size={16} className="text-gray-400" />}
      </button>
      {expanded && <div className="border-t border-gray-100">{children}</div>}
    </div>
  )
}

export default function Generate() {
  const [companyUrl, setCompanyUrl] = useState('')
  const [input, setInput] = useState('')
  const [allText, setAllText] = useState('')
  const [info, setInfo] = useState({ company: false, audience: false, goal: false, channel: false })
  const [phase, setPhase] = useState('input')
  const [campaigns, setCampaigns] = useState([])
  const [selectedCampaign, setSelectedCampaign] = useState(null)
  const [generating, setGenerating] = useState(false)
  const [genError, setGenError] = useState('')
  const [progress, setProgress] = useState('')
  const [progressStep, setProgressStep] = useState({ step: null, total: null })
  const [agentOutputs, setAgentOutputs] = useState({
    signals: [],
    campaigns: [],
    distributionPlans: [],
  })
  const [expandedAgents, setExpandedAgents] = useState({
    signals: true,
    campaigns: false,
    distribution: false,
  })
  const textareaRef = useRef(null)

  const hasUrl = isValidUrl(companyUrl)
  const completed = countCompleted(info) + (hasUrl ? 1 : 0)
  const isReady = hasUrl && countCompleted(info) >= 3

  const autoGrow = useCallback(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = '52px'
    el.style.height = Math.min(el.scrollHeight, 160) + 'px'
  }, [])

  useEffect(() => {
    const combined = allText + ' ' + input
    setInfo(detectCampaignInfo(combined))
  }, [input, allText])

  const addTag = (text) => {
    setInput(prev => (prev ? prev + ' ' + text : text))
    textareaRef.current?.focus()
    setTimeout(autoGrow, 0)
  }

  const sendMessage = () => {
    if (!input.trim()) return
    setAllText(prev => (prev ? prev + ' ' : '') + input.trim())
    setInput('')
    setTimeout(autoGrow, 0)
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  const generateCampaigns = async () => {
    setGenerating(true)
    setGenError('')
    setProgress('Surfacing trend signals...')
    setProgressStep({ step: null, total: null })
    setAgentOutputs({ signals: [], campaigns: [], distributionPlans: [] })
    setPhase('loading')

    try {
      let companyId = null
      const website = normalizeWebsiteUrl(companyUrl)
      const combinedContext = [allText, input].filter(Boolean).join(' ').trim()

      if (website) {
        setProgress('Saving company profile...')
        const intakeRes = await apiFetch('/api/company/intake', {
          method: 'POST',
          body: JSON.stringify({
            companyName: deriveCompanyNameFromWebsite(website),
            website,
            industry: 'General',
            description: combinedContext || null,
            audience: null,
            tone: null,
            goals: null,
            avoidTopics: null,
            fast_mode: true,
          }),
        })
        if (!intakeRes?.success) {
          throw new Error(intakeRes?.message || 'Failed to save company profile')
        }
        companyId = intakeRes?.company_id || null
      }

      if (!companyId) {
        try {
          const profile = await apiFetch('/api/company/profile')
          companyId = profile?.id || null
        } catch {
          // backend can still fallback to latest profile when available
        }
      }

      setProgress('Running campaign generation (Agent 3 + 4)...')
      const result = await submitAndPoll(
        '/api/campaigns/generate',
        { company_id: companyId, n_concepts: 3 },
        {
          intervalMs: 3000,
          timeoutMs: 120000,
          onProgress: (job) => {
            if (job.status === 'queued') {
              setProgress('Queued...')
              return
            }
            if (job.status === 'running') {
              setProgress(job.progress_message || 'Generating campaigns...')
              if (typeof job.progress_step === 'number' && typeof job.progress_total === 'number') {
                setProgressStep({ step: job.progress_step, total: job.progress_total })
              }
            }
          },
        }
      )

      const signalMap = {}
      for (const sig of (result?.signals_used || [])) {
        signalMap[sig.id] = sig
      }

      const rawCampaigns = result?.campaigns || []
      const normalized = rawCampaigns.map(c => normalizeCampaign(c, signalMap))
      setCampaigns(normalized)
      setAgentOutputs({
        signals: result?.signals_used || [],
        campaigns: rawCampaigns,
        distributionPlans: normalizeDistributionPlans(result?.distribution_plans || []),
      })
      setPhase('results')
    } catch (err) {
      setGenError(err.message)
      setPhase('input')
    } finally {
      setGenerating(false)
      setProgress('')
      setProgressStep({ step: null, total: null })
    }
  }

  if (phase === 'loading') {
    return (
      <div className="flex-1 flex flex-col items-center justify-center px-10">
        <Loader2 size={40} className="animate-spin text-brand mb-4" />
        <p className="text-[15px] font-semibold text-gray-700">{progress || 'Generating campaigns...'}</p>
        {progressStep.step && progressStep.total ? (
          <p className="text-xs text-gray-500 mt-1">Step {progressStep.step} of {progressStep.total}</p>
        ) : null}
        <p className="text-sm text-gray-400 mt-1">Agent 2 -&gt; Agent 3 -&gt; Agent 4 pipeline running</p>
      </div>
    )
  }

  if (phase === 'results') {
    const userText = allText || input || 'Campaign generation request'
    const contextLines = []
    if (companyUrl?.trim()) contextLines.push(`Website: ${companyUrl.trim()}`)
    contextLines.push(userText)
    const contextDisplay = contextLines.join('\n\n')
    const { signalsText, campaignsText, distributionText } = buildAgentTextOutputs(agentOutputs)

    return (
      <div className="flex flex-col h-full w-full overflow-hidden">
        <div className="px-8 py-4 bg-white border-b border-gray-200 shrink-0">
          <div className="flex items-end gap-2 border border-gray-200 rounded-card p-1.5 shadow-card">
            <textarea
              ref={textareaRef}
              className="flex-1 border-none outline-none resize-none text-[15px] text-gray-900 px-4 py-3 bg-transparent min-h-[52px] max-h-[160px] font-sans leading-relaxed"
              placeholder="Refine your campaign..."
              rows={1}
            />
            <button
              onClick={generateCampaigns}
              disabled={generating}
              className="w-10 h-10 rounded-[10px] bg-brand grid place-items-center shrink-0 mr-1 mb-1 hover:bg-brand-700 transition-fast disabled:opacity-50"
            >
              {generating ? <Loader2 size={18} className="text-white animate-spin" /> : <Send size={18} className="text-white" />}
            </button>
          </div>
        </div>

        <div className="flex-1 flex overflow-hidden">
          {/* Main Left Pane - Campaign Concepts */}
          <div className="flex-1 overflow-y-auto px-8 py-7 custom-scrollbar">
            <div className="mb-5 fade-in">
              <div className="flex gap-3 mb-4">
                <div className="w-7 h-7 rounded-lg bg-surface-alt border border-gray-200 grid place-items-center text-[11px] font-bold text-gray-400 shrink-0">E</div>
                <p className="text-sm text-gray-900 leading-relaxed max-w-[560px] whitespace-pre-line">{contextDisplay}</p>
              </div>
              <div className="flex gap-3">
                <div className="w-7 h-7 rounded-lg bg-brand grid place-items-center text-[11px] font-bold text-white shrink-0">S</div>
                <p className="text-sm text-gray-500 leading-relaxed max-w-[560px]">
                  Based on your brand profile and live Polymarket signals, here are{' '}
                  {campaigns.length} campaign {campaigns.length === 1 ? 'concept' : 'concepts'} ranked by confidence.
                </p>
              </div>
            </div>

            {genError && (
              <p className="mb-4 text-sm text-red-600 bg-red-50 px-4 py-2 rounded-lg">{genError}</p>
            )}

            <div className="flex items-center justify-between mb-6 fade-in">
              <h2 className="text-xl font-extrabold text-gray-900 tracking-tight">Proposed Campaigns</h2>
              <span className="inline-flex items-center gap-1.5 px-3 py-[5px] rounded-full text-xs font-semibold bg-emerald-50 text-emerald-600">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 pulse-dot" />
                {campaigns.length} generated
              </span>
            </div>

            <div className="flex flex-col gap-4 fade-in">
              {campaigns.map((campaign, i) => (
                <CampaignCard
                  key={campaign.id}
                  campaign={campaign}
                  rank={i + 1}
                  selected={selectedCampaign === campaign.id}
                  onSelect={setSelectedCampaign}
                />
              ))}
            </div>

            <div className="flex items-center justify-between mt-6 pt-5 border-t border-gray-100 fade-in">
              <button
                onClick={() => {
                  setPhase('input')
                  setSelectedCampaign(null)
                  setCampaigns([])
                  setAgentOutputs({ signals: [], campaigns: [], distributionPlans: [] })
                }}
                className="inline-flex items-center gap-1.5 px-4 py-2.5 rounded-[10px] border border-gray-200 bg-white text-[13px] font-semibold text-gray-500 hover:bg-surface-alt hover:text-gray-900 transition-fast"
              >
                <RotateCcw size={16} />
                Start over
              </button>
              <button
                disabled={!selectedCampaign || generating}
                onClick={async () => {
                  if (!selectedCampaign) return
                  setGenerating(true)
                  setGenError('')
                  try {
                    await apiFetch(`/api/campaigns/${selectedCampaign}/approve`, { method: 'POST' })
                    await submitAndPoll(
                      '/api/content/strategies/generate',
                      { campaign_id: selectedCampaign },
                      { intervalMs: 3000, timeoutMs: 120000 }
                    )
                  } catch (err) {
                    setGenError(err.message || 'Failed to approve campaign')
                  }
                  setGenerating(false)
                }}
                className="px-6 py-2.5 rounded-[10px] bg-brand text-white text-sm font-bold shadow-[0_2px_8px_rgba(0,102,255,0.2)] hover:bg-brand-700 hover:-translate-y-px transition-fast disabled:opacity-40 disabled:cursor-not-allowed disabled:transform-none"
              >
                {generating ? 'Approving...' : 'Approve selected ->'}
              </button>
            </div>
          </div>

          {/* Right Pane - Agent Generation Text */}
          <div className="w-[450px] shrink-0 border-l border-gray-200 bg-gray-50 flex flex-col overflow-hidden">
            <div className="px-5 py-4 border-b border-gray-200 bg-white shrink-0">
              <h3 className="text-sm font-bold text-gray-900 flex items-center gap-2">
                <Loader2 size={16} className={cn("text-brand", generating && "animate-spin")} />
                Agent Output Text
              </h3>
              <p className="text-xs text-gray-500 mt-1">Raw generations from Agents 2, 3, and 4</p>
            </div>
            
            <div className="flex-1 overflow-y-auto p-4 custom-scrollbar flex flex-col gap-4">
              <div className="rounded-xl border border-gray-200 bg-white overflow-hidden shadow-sm">
                <div className="px-4 py-2.5 border-b border-gray-100 bg-gray-50/50 flex justify-between items-center">
                  <h4 className="text-xs font-bold text-gray-700 uppercase tracking-wide">Agent 2: Signals</h4>
                </div>
                <div className="p-3 bg-white">
                  <pre className="text-[11px] text-gray-600 whitespace-pre-wrap break-words font-mono leading-relaxed">{signalsText}</pre>
                </div>
              </div>
              
              <div className="rounded-xl border border-gray-200 bg-white overflow-hidden shadow-sm">
                <div className="px-4 py-2.5 border-b border-gray-100 bg-gray-50/50 flex justify-between items-center">
                  <h4 className="text-xs font-bold text-gray-700 uppercase tracking-wide">Agent 3: Campaigns</h4>
                </div>
                <div className="p-3 bg-white">
                  <pre className="text-[11px] text-gray-600 whitespace-pre-wrap break-words font-mono leading-relaxed">{campaignsText}</pre>
                </div>
              </div>
              
              <div className="rounded-xl border border-gray-200 bg-white overflow-hidden shadow-sm">
                <div className="px-4 py-2.5 border-b border-gray-100 bg-gray-50/50 flex justify-between items-center">
                  <h4 className="text-xs font-bold text-gray-700 uppercase tracking-wide">Agent 4: Distribution</h4>
                </div>
                <div className="p-3 bg-white">
                  <pre className="text-[11px] text-gray-600 whitespace-pre-wrap break-words font-mono leading-relaxed">{distributionText}</pre>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="flex-1 flex flex-col items-center justify-center px-10 transition-layout">
      <h1 className="text-[32px] font-extrabold text-gray-900 tracking-tight mb-1.5 text-center">
        Create your first campaign
      </h1>
      <p className="text-[15px] text-gray-500 text-center mb-8">
        Tell us about your company and goals. We'll match you with trending signals and generate campaigns.
      </p>

      {genError && (
        <p className="mb-4 text-sm text-red-600 bg-red-50 px-4 py-2 rounded-lg max-w-[680px] w-full">{genError}</p>
      )}

      <div className="w-full max-w-[680px] mb-4">
        <label className="block text-sm font-semibold text-gray-700 mb-1.5">
          <span className="inline-flex items-center gap-1.5">
            <Globe size={16} className="text-brand" />
            Company website
          </span>
          <span className="text-red-500 ml-0.5">*</span>
        </label>
        <input
          type="url"
          value={companyUrl}
          onChange={(e) => setCompanyUrl(e.target.value)}
          placeholder="https://yourcompany.com or yourcompany.com"
          className={cn(
            'w-full px-4 py-3 rounded-xl border text-[15px] text-gray-900 placeholder:text-gray-400 outline-none transition-fast',
            hasUrl
              ? 'border-emerald-300 bg-emerald-50/50 focus:border-brand focus:ring-2 focus:ring-brand/10'
              : 'border-gray-200 focus:border-brand focus:ring-2 focus:ring-brand/10'
          )}
        />
        <p className="mt-1 text-xs text-gray-500">We use this to understand your brand and match you with relevant signals.</p>
      </div>

      <div className="w-full max-w-[680px]">
        <div className="bg-white border-[1.5px] border-gray-200 rounded-2xl p-1.5 shadow-card-md input-focus-ring transition-med">
          <div className="flex items-end gap-2">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => {
                setInput(e.target.value)
                autoGrow()
              }}
              onKeyDown={handleKeyDown}
              rows={1}
              className="flex-1 border-none outline-none resize-none text-[15px] text-gray-900 px-4 pt-3.5 pb-2 bg-transparent min-h-[52px] max-h-[160px] font-sans leading-relaxed placeholder:text-gray-300"
              placeholder="Describe your company, product, audience, and campaign goals..."
            />
            <button
              onClick={sendMessage}
              disabled={!input.trim()}
              className="w-10 h-10 rounded-[10px] bg-brand grid place-items-center shrink-0 mr-1 mb-1 hover:bg-brand-700 hover:scale-105 transition-fast disabled:opacity-30 disabled:cursor-not-allowed disabled:scale-100"
            >
              <Send size={18} className="text-white" />
            </button>
          </div>

          <div className="flex items-center gap-1.5 px-3.5 pb-2.5 flex-wrap">
            {TAG_SUGGESTIONS.map((tag) => (
              <button
                key={tag.label}
                onClick={() => addTag(tag.text)}
                className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium border border-gray-100 bg-surface-alt text-gray-500 hover:border-gray-200 hover:bg-white transition-fast"
              >
                <Plus size={12} />
                {tag.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="w-full max-w-[680px] mt-6">
        <div className="flex items-center gap-3 mb-4">
          <div className="flex-1 h-1.5 bg-surface-alt rounded-full overflow-hidden">
            <div
              className="h-full rounded-full bg-brand progress-animate"
              style={{ width: `${(completed / 5) * 100}%` }}
            />
          </div>
          <span className="text-xs font-semibold text-gray-400 whitespace-nowrap">
            {completed} / 5 completed
          </span>
        </div>

        <div className="grid grid-cols-2 gap-2">
          <ChecklistItem label="Company website" done={hasUrl} />
          <ChecklistItem label="Company or product info" done={info.company} />
          <ChecklistItem label="Target audience" done={info.audience} />
          <ChecklistItem label="Campaign goals" done={info.goal} />
          <ChecklistItem label="Preferred channels" done={info.channel} />
        </div>

        <div
          className={cn(
            'flex justify-center mt-5 transition-all duration-300',
            isReady ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-2 pointer-events-none'
          )}
        >
          <button
            onClick={generateCampaigns}
            disabled={generating}
            className="px-8 py-3 rounded-[10px] bg-brand text-white text-[15px] font-bold shadow-[0_2px_8px_rgba(0,102,255,0.25)] hover:bg-brand-700 hover:-translate-y-px hover:shadow-[0_4px_16px_rgba(0,102,255,0.3)] transition-fast disabled:opacity-50"
          >
            {generating ? 'Generating...' : 'Generate Campaigns ->'}
          </button>
        </div>
      </div>
    </div>
  )
}

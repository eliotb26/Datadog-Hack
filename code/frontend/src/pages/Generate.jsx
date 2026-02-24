import { useState, useRef, useCallback, useEffect } from 'react'
import { Send, RotateCcw, Plus, Loader2, Globe, ChevronDown, ChevronRight } from 'lucide-react'
import { cn, detectCampaignInfo, countCompleted } from '@/lib/utils'
import { submitJob, pollJob, submitAndPoll, apiFetch } from '@/lib/api'
import CampaignCard from '@/components/CampaignCard'
import ChecklistItem from '@/components/ChecklistItem'

const TAG_SUGGESTIONS = [
  { label: 'Company type', text: 'We are a fintech SaaS company' },
  { label: 'Audience', text: 'targeting B2B enterprise customers' },
  { label: 'Campaign goal', text: 'our goal is brand awareness and thought leadership' },
  { label: 'Channels', text: 'we want to post on LinkedIn and Twitter' },
]

const GENERATE_STATE_KEY = 'onlygen_generate_state_v1'
const GENERATE_ACTIVE_JOB_KEY = 'onlygen_generate_active_job_v1'
const EMPTY_PROGRESS_STEP = { step: null, total: null }
const EMPTY_AGENT_OUTPUTS = {
  signals: [],
  campaigns: [],
  distributionPlans: [],
  feedback: null,
  contentStrategies: [],
  contentPieces: [],
}
const EMPTY_AGENT_PANELS = {
  agent1: { title: 'Agent 1: Brand Intake', status: 'idle', text: 'Waiting to ingest company profile.' },
  agent2: { title: 'Agent 2: Signals', status: 'idle', text: 'Waiting to surface trend signals.' },
  agent3: { title: 'Agent 3: Campaigns', status: 'idle', text: 'Waiting to generate campaign concepts.' },
  agent4: { title: 'Agent 4: Distribution', status: 'idle', text: 'Waiting to route channels.' },
  agent5: { title: 'Agent 5: Feedback Loop', status: 'idle', text: 'Waiting to run optimization loops.' },
  agent6: { title: 'Agent 6: Content Strategy', status: 'idle', text: 'Waiting to choose content format.' },
  agent7: { title: 'Agent 7: Content Production', status: 'idle', text: 'Waiting to generate content pieces.' },
}

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

  const feedback = agentOutputs.feedback || null
  const feedbackText = feedback
    ? [
      feedback.success === false ? `Status: failed` : `Status: completed`,
      feedback.loop1 ? `Loop 1 campaigns analyzed: ${feedback.loop1.campaigns_analyzed || 0}` : null,
      feedback.loop2 ? `Loop 2 patterns discovered: ${feedback.loop2.patterns_discovered || 0}` : null,
      feedback.loop3 ? `Loop 3 calibrations updated: ${feedback.loop3.calibrations_updated || 0}` : null,
      feedback.error ? `Error: ${feedback.error}` : null,
    ].filter(Boolean).join('\n')
    : 'No feedback-loop output generated.'

  const strategyText = (agentOutputs.contentStrategies || []).map((s, idx) => {
    const priority = Math.round((s.priority_score || 0) * 100)
    return [
      `${idx + 1}. ${s.content_type || 'unknown'} (${priority}% priority)`,
      s.reasoning || 'No reasoning provided.',
    ].join('\n')
  }).join('\n\n')

  const productionText = (agentOutputs.contentPieces || []).map((p, idx) => {
    return [
      `${idx + 1}. ${p.title || 'Untitled content'} (${p.content_type || 'unknown'})`,
      `Word count: ${p.word_count || 0} | Quality: ${Math.round((p.quality_score || 0) * 100)}%`,
      p.summary || 'No summary provided.',
    ].join('\n')
  }).join('\n\n')

  return {
    signalsText: signalsText || 'No signal text generated.',
    campaignsText: campaignsText || 'No campaign text generated.',
    distributionText: distributionText || 'No distribution text generated.',
    feedbackText: feedbackText || 'No feedback-loop output generated.',
    strategyText: strategyText || 'No content-strategy output generated.',
    productionText: productionText || 'No content-production output generated.',
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

function StrategyAndContentSection({ selectedCampaign, strategies = [], pieces = [], generating }) {
  const selectedStrategies = (strategies || []).filter((s) => s.campaign_id === selectedCampaign)

  const strategyIds = new Set(selectedStrategies.map((s) => s.id))
  const selectedPieces = (pieces || []).filter((p) => strategyIds.has(p.strategy_id))

  const hasSelectedContent = selectedStrategies.length > 0 || selectedPieces.length > 0

  if (!selectedCampaign) return null

  return (
    <div className="mt-6 pt-5 border-t border-gray-100 fade-in">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-extrabold text-gray-900 tracking-tight">Approved Campaign Content</h3>
        <span className="text-xs font-semibold text-gray-500">
          {selectedPieces.length} piece{selectedPieces.length === 1 ? '' : 's'}
        </span>
      </div>

      {!hasSelectedContent ? (
        <p className="text-sm text-gray-500 bg-gray-50 border border-gray-100 rounded-xl px-4 py-3">
          {generating
            ? 'Generating content for this approved campaign...'
            : 'Approve the selected campaign to generate and view content here.'}
        </p>
      ) : (
        <div className="flex flex-col gap-4">
          {selectedStrategies.map((strategy) => (
            <div key={strategy.id} className="rounded-xl border border-gray-200 bg-white overflow-hidden">
              <div className="px-4 py-3 border-b border-gray-100 bg-gray-50/50">
                <p className="text-sm font-bold text-gray-900 capitalize">{strategy.content_type || 'content strategy'}</p>
                {strategy.reasoning && <p className="text-xs text-gray-500 mt-0.5">{strategy.reasoning}</p>}
              </div>
              <div className="p-4">
                {selectedPieces.filter((piece) => piece.strategy_id === strategy.id).length === 0 ? (
                  <p className="text-sm text-gray-500">No generated content piece for this strategy yet.</p>
                ) : (
                  <div className="flex flex-col gap-3">
                    {selectedPieces
                      .filter((piece) => piece.strategy_id === strategy.id)
                      .map((piece) => (
                        <div key={piece.id} className="rounded-lg border border-gray-100 bg-gray-50 px-4 py-3">
                          <p className="text-sm font-semibold text-gray-900">{piece.title || 'Generated content'}</p>
                          <p className="text-[11px] text-gray-500 mt-0.5">
                            {piece.content_type || 'content'} • {piece.word_count || 0} words • quality {Math.round((piece.quality_score || 0) * 100)}%
                          </p>
                          <div className="mt-2 text-sm text-gray-700 whitespace-pre-wrap">
                            {piece.body || piece.content || piece.summary || 'No content body returned.'}
                          </div>
                        </div>
                      ))}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
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
  const [progressStep, setProgressStep] = useState(EMPTY_PROGRESS_STEP)
  const [agentOutputs, setAgentOutputs] = useState(EMPTY_AGENT_OUTPUTS)
  const [agentPanels, setAgentPanels] = useState(EMPTY_AGENT_PANELS)
  const [expandedAgents, setExpandedAgents] = useState({
    signals: true,
    campaigns: false,
    distribution: false,
  })
  const textareaRef = useRef(null)
  const hydratedRef = useRef(false)

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

  const clearPersistedState = useCallback(() => {
    sessionStorage.removeItem(GENERATE_STATE_KEY)
    sessionStorage.removeItem(GENERATE_ACTIVE_JOB_KEY)
  }, [])

  const setAgentPanel = useCallback((id, patch) => {
    setAgentPanels((prev) => ({
      ...prev,
      [id]: {
        ...(prev[id] || {}),
        ...patch,
      },
    }))
  }, [])

  const applyGenerationResult = useCallback((result) => {
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
      feedback: result?.feedback || null,
      contentStrategies: result?.content_strategies || [],
      contentPieces: result?.content_pieces || [],
    })
    setPhase('results')
  }, [])

  const runPollingForJob = useCallback(async (jobId) => {
    sessionStorage.setItem(GENERATE_ACTIVE_JOB_KEY, jobId)
    setGenError('')
    setPhase('loading')

    try {
      const result = await pollJob(jobId, {
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
            const msg = String(job.progress_message || '')
            if (msg.includes('Agent 2')) setAgentPanel('agent2', { status: 'running' })
            if (msg.includes('Agent 3')) setAgentPanel('agent3', { status: 'running' })
            if (msg.includes('Agent 4')) setAgentPanel('agent4', { status: 'running' })
          }
        },
      })

      applyGenerationResult(result)
      return result
    } catch (err) {
      setGenError(err.message)
      setPhase('input')
      throw err
    } finally {
      setProgress('')
      setProgressStep(EMPTY_PROGRESS_STEP)
      sessionStorage.removeItem(GENERATE_ACTIVE_JOB_KEY)
    }
  }, [applyGenerationResult, setAgentPanel])

  useEffect(() => {
    try {
      const raw = sessionStorage.getItem(GENERATE_STATE_KEY)
      if (raw) {
        const saved = JSON.parse(raw)
        setCompanyUrl(saved.companyUrl || '')
        setInput(saved.input || '')
        setAllText(saved.allText || '')
        setPhase(saved.phase || 'input')
        setCampaigns(Array.isArray(saved.campaigns) ? saved.campaigns : [])
        setSelectedCampaign(saved.selectedCampaign || null)
        setGenError(saved.genError || '')
        setProgress(saved.progress || '')
        setProgressStep(saved.progressStep || EMPTY_PROGRESS_STEP)
        setAgentOutputs(saved.agentOutputs || EMPTY_AGENT_OUTPUTS)
        setAgentPanels(saved.agentPanels || EMPTY_AGENT_PANELS)
        setExpandedAgents(saved.expandedAgents || { signals: true, campaigns: false, distribution: false })
      }
    } catch {
      clearPersistedState()
    } finally {
      hydratedRef.current = true
    }

    const activeJobId = sessionStorage.getItem(GENERATE_ACTIVE_JOB_KEY)
    if (activeJobId) {
      setGenerating(true)
      runPollingForJob(activeJobId).finally(() => setGenerating(false))
    }
  }, [clearPersistedState, runPollingForJob])

  useEffect(() => {
    if (!hydratedRef.current) return
    const state = {
      companyUrl,
      input,
      allText,
      phase,
      campaigns,
      selectedCampaign,
      genError,
      progress,
      progressStep,
      agentOutputs,
      agentPanels,
      expandedAgents,
    }
    sessionStorage.setItem(GENERATE_STATE_KEY, JSON.stringify(state))
  }, [
    companyUrl,
    input,
    allText,
    phase,
    campaigns,
    selectedCampaign,
    genError,
    progress,
    progressStep,
    agentOutputs,
    agentPanels,
    expandedAgents,
  ])

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
    setProgress('Starting Agent 1...')
    setProgressStep({ step: 1, total: 7 })
    setAgentOutputs(EMPTY_AGENT_OUTPUTS)
    setAgentPanels(EMPTY_AGENT_PANELS)
    setPhase('loading')

    try {
      let companyId = null
      const website = normalizeWebsiteUrl(companyUrl)
      const combinedContext = [allText, input].filter(Boolean).join(' ').trim()

      if (website) {
        setAgentPanel('agent1', { status: 'running', text: 'Ingesting company profile and brand context...' })
        setProgress('Agent 1: Saving company profile...')
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
        setAgentPanel('agent1', {
          status: 'completed',
          text: intakeRes?.message || intakeRes?.agent_response || `Company profile saved (${companyId || 'no id returned'})`,
        })
      }

      if (!companyId) {
        try {
          const profile = await apiFetch('/api/company/profile')
          companyId = profile?.id || null
          setAgentPanel('agent1', {
            status: 'completed',
            text: `Loaded existing company profile${companyId ? ` (${companyId})` : ''}.`,
          })
        } catch {
          // backend can still fallback to latest profile when available
          setAgentPanel('agent1', {
            status: 'failed',
            text: 'Could not load company profile directly; using backend fallback.',
          })
        }
      }

      setProgress('Running Agents 2-4...')
      const { job_id } = await submitJob(
        '/api/campaigns/generate',
        { company_id: companyId, n_concepts: 3 }
      )
      const campaignResult = await runPollingForJob(job_id)
      const textOutputs = buildAgentTextOutputs({
        signals: campaignResult?.signals_used || [],
        campaigns: campaignResult?.campaigns || [],
        distributionPlans: normalizeDistributionPlans(campaignResult?.distribution_plans || []),
      })
      setAgentPanel('agent2', { status: 'completed', text: textOutputs.signalsText })
      setAgentPanel('agent3', { status: 'completed', text: textOutputs.campaignsText })
      setAgentPanel('agent4', { status: 'completed', text: textOutputs.distributionText })

      setProgress('Agent 5: Running feedback loop...')
      setProgressStep({ step: 5, total: 7 })
      setAgentPanel('agent5', { status: 'running', text: 'Analyzing campaign outcomes and updating prompt weights...' })
      try {
        const feedbackRes = await submitAndPoll(
          '/api/feedback/trigger',
          { company_id: companyId, run_loop1: true, run_loop2: true, run_loop3: true },
          { intervalMs: 3000, timeoutMs: 120000 }
        )
        setAgentOutputs((prev) => ({ ...prev, feedback: feedbackRes }))
        const feedbackText = buildAgentTextOutputs({
          ...EMPTY_AGENT_OUTPUTS,
          feedback: feedbackRes,
        }).feedbackText
        setAgentPanel('agent5', {
          status: feedbackRes?.success === false ? 'failed' : 'completed',
          text: feedbackText,
        })
      } catch (e) {
        setAgentPanel('agent5', { status: 'failed', text: e.message || 'Feedback loop failed.' })
      }

      const firstCampaignId = campaignResult?.campaigns?.[0]?.id
      if (firstCampaignId) {
        setProgress('Agent 6: Generating content strategy...')
        setProgressStep({ step: 6, total: 7 })
        setAgentPanel('agent6', { status: 'running', text: 'Selecting the best format for the top campaign...' })
        let strategies = []
        try {
          const strategyRes = await submitAndPoll(
            '/api/content/strategies/generate',
            { campaign_id: firstCampaignId },
            { intervalMs: 3000, timeoutMs: 120000 }
          )
          strategies = strategyRes?.strategies || []
          setAgentOutputs((prev) => ({ ...prev, contentStrategies: strategies }))
          const strategyText = buildAgentTextOutputs({
            ...EMPTY_AGENT_OUTPUTS,
            contentStrategies: strategies,
          }).strategyText
          setAgentPanel('agent6', { status: 'completed', text: strategyText })
        } catch (e) {
          setAgentPanel('agent6', { status: 'failed', text: e.message || 'Content strategy generation failed.' })
        }

        const firstStrategyId = strategies?.[0]?.id
        if (firstStrategyId) {
          setProgress('Agent 7: Producing content...')
          setProgressStep({ step: 7, total: 7 })
          setAgentPanel('agent7', { status: 'running', text: 'Generating publish-ready content from strategy...' })
          try {
            const pieceRes = await submitAndPoll(
              '/api/content/pieces/generate',
              { strategy_id: firstStrategyId },
              { intervalMs: 3000, timeoutMs: 120000 }
            )
            const pieces = pieceRes?.pieces || []
            setAgentOutputs((prev) => ({ ...prev, contentPieces: pieces }))
            const productionText = buildAgentTextOutputs({
              ...EMPTY_AGENT_OUTPUTS,
              contentPieces: pieces,
            }).productionText
            setAgentPanel('agent7', { status: 'completed', text: productionText })
          } catch (e) {
            setAgentPanel('agent7', { status: 'failed', text: e.message || 'Content production failed.' })
          }
        } else {
          setAgentPanel('agent7', { status: 'failed', text: 'No strategy available for content generation.' })
        }
      } else {
        setAgentPanel('agent6', { status: 'failed', text: 'No campaign available for strategy generation.' })
        setAgentPanel('agent7', { status: 'failed', text: 'No strategy available for content generation.' })
      }
      setProgress('All 7 agents completed.')
      setProgressStep({ step: 7, total: 7 })
    } catch (err) {
      setGenError(err.message)
      setPhase('input')
    } finally {
      setGenerating(false)
    }
  }

  const approveCampaignAndRunNextStages = async () => {
    if (!selectedCampaign) return
    setGenerating(true)
    setGenError('')
    setProgress('Approving selected campaign...')
    setProgressStep({ step: 6, total: 7 })

    try {
      await apiFetch(`/api/campaigns/${selectedCampaign}/approve`, { method: 'POST' })

      setProgress('Agent 6: Generating content strategy...')
      setAgentPanel('agent6', { status: 'running', text: 'Selecting the best content format for the approved campaign...' })

      const strategyRes = await submitAndPoll(
        '/api/content/strategies/generate',
        { campaign_id: selectedCampaign },
        { intervalMs: 3000, timeoutMs: 120000 }
      )
      const strategies = strategyRes?.strategies || []
      setAgentOutputs((prev) => ({ ...prev, contentStrategies: strategies }))
      const strategyText = buildAgentTextOutputs({
        ...EMPTY_AGENT_OUTPUTS,
        contentStrategies: strategies,
      }).strategyText
      setAgentPanel('agent6', { status: 'completed', text: strategyText })

      const firstStrategyId = strategies?.[0]?.id
      if (!firstStrategyId) {
        setAgentPanel('agent7', { status: 'failed', text: 'No strategy available for content generation.' })
        throw new Error('Campaign approved, but no strategy was generated.')
      }

      setProgress('Agent 7: Producing content...')
      setProgressStep({ step: 7, total: 7 })
      setAgentPanel('agent7', { status: 'running', text: 'Generating publish-ready content from approved campaign strategy...' })

      const pieceRes = await submitAndPoll(
        '/api/content/pieces/generate',
        { strategy_id: firstStrategyId },
        { intervalMs: 3000, timeoutMs: 120000 }
      )
      const pieces = pieceRes?.pieces || []
      setAgentOutputs((prev) => ({ ...prev, contentPieces: pieces }))
      const productionText = buildAgentTextOutputs({
        ...EMPTY_AGENT_OUTPUTS,
        contentPieces: pieces,
      }).productionText
      setAgentPanel('agent7', { status: 'completed', text: productionText })
      setProgress('Campaign approved and downstream stages completed.')
    } catch (err) {
      setGenError(err.message || 'Failed to approve campaign and run next stages')
    } finally {
      setGenerating(false)
    }
  }

  const renderAgentOutputPane = () => (
    <div className="w-[450px] shrink-0 border-l border-gray-200 bg-gray-50 flex flex-col overflow-hidden">
      <div className="px-5 py-4 border-b border-gray-200 bg-white shrink-0">
        <h3 className="text-sm font-bold text-gray-900 flex items-center gap-2">
          <Loader2 size={16} className={cn("text-brand", generating && "animate-spin")} />
          Agent Output Text
        </h3>
        <p className="text-xs text-gray-500 mt-1">Live generations from Agents 1 through 7</p>
      </div>

      <div className="flex-1 overflow-y-auto p-4 custom-scrollbar flex flex-col gap-4">
        {Object.entries(agentPanels).map(([key, panel]) => (
          <div key={key} className="rounded-xl border border-gray-200 bg-white overflow-hidden shadow-sm">
            <div className="px-4 py-2.5 border-b border-gray-100 bg-gray-50/50 flex justify-between items-center">
              <h4 className="text-xs font-bold text-gray-700 uppercase tracking-wide">{panel.title}</h4>
              <span
                className={cn(
                  'text-[10px] px-2 py-0.5 rounded-full font-semibold uppercase tracking-wide',
                  panel.status === 'completed' && 'bg-emerald-100 text-emerald-700',
                  panel.status === 'running' && 'bg-blue-100 text-blue-700',
                  panel.status === 'failed' && 'bg-red-100 text-red-700',
                  panel.status === 'idle' && 'bg-gray-100 text-gray-600'
                )}
              >
                {panel.status}
              </span>
            </div>
            <div className="p-3 bg-white">
              <pre className="text-[11px] text-gray-600 whitespace-pre-wrap break-words font-mono leading-relaxed">
                {panel.text || 'No output yet.'}
              </pre>
            </div>
          </div>
        ))}
      </div>
    </div>
  )

  if (phase === 'loading') {
    return (
      <div className="flex-1 flex overflow-hidden">
        <div className="flex-1 flex flex-col items-center justify-center px-10">
          <Loader2 size={40} className="animate-spin text-brand mb-4" />
          <p className="text-[15px] font-semibold text-gray-700">{progress || 'Generating campaigns...'}</p>
          {progressStep.step && progressStep.total ? (
            <p className="text-xs text-gray-500 mt-1">Step {progressStep.step} of {progressStep.total}</p>
          ) : null}
          <p className="text-sm text-gray-400 mt-1">Running the full 7-agent pipeline</p>
        </div>
        {renderAgentOutputPane()}
      </div>
    )
  }

  if (phase === 'results') {
    const userText = allText || input || 'Campaign generation request'
    const contextLines = []
    if (companyUrl?.trim()) contextLines.push(`Website: ${companyUrl.trim()}`)
    contextLines.push(userText)
    const contextDisplay = contextLines.join('\n\n')
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
                  setAgentOutputs(EMPTY_AGENT_OUTPUTS)
                  setAgentPanels(EMPTY_AGENT_PANELS)
                  setProgress('')
                  setProgressStep(EMPTY_PROGRESS_STEP)
                  clearPersistedState()
                }}
                className="inline-flex items-center gap-1.5 px-4 py-2.5 rounded-[10px] border border-gray-200 bg-white text-[13px] font-semibold text-gray-500 hover:bg-surface-alt hover:text-gray-900 transition-fast"
              >
                <RotateCcw size={16} />
                Start over
              </button>
              <button
                disabled={!selectedCampaign || generating}
                onClick={approveCampaignAndRunNextStages}
                className="px-6 py-2.5 rounded-[10px] bg-brand text-white text-sm font-bold shadow-[0_2px_8px_rgba(0,102,255,0.2)] hover:bg-brand-700 hover:-translate-y-px transition-fast disabled:opacity-40 disabled:cursor-not-allowed disabled:transform-none"
              >
                {generating ? 'Approving + running stages...' : 'Approve selected ->'}
              </button>
            </div>

            <StrategyAndContentSection
              selectedCampaign={selectedCampaign}
              strategies={agentOutputs.contentStrategies}
              pieces={agentOutputs.contentPieces}
              generating={generating}
            />
          </div>

          {renderAgentOutputPane()}
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

import { useState, useRef, useCallback, useEffect } from 'react'
import { Send, RotateCcw, Plus } from 'lucide-react'
import { cn, detectCampaignInfo, countCompleted, MOCK_CAMPAIGNS } from '@/lib/utils'
import CampaignCard from '@/components/CampaignCard'
import ChecklistItem from '@/components/ChecklistItem'

const TAG_SUGGESTIONS = [
  { label: 'Company type', text: 'We are a fintech SaaS company' },
  { label: 'Audience', text: 'targeting B2B enterprise customers' },
  { label: 'Campaign goal', text: 'our goal is brand awareness and thought leadership' },
  { label: 'Channels', text: 'we want to post on LinkedIn and Twitter' },
]

export default function Generate() {
  const [input, setInput] = useState('')
  const [allText, setAllText] = useState('')
  const [info, setInfo] = useState({ company: false, audience: false, goal: false, channel: false })
  const [phase, setPhase] = useState('input') // 'input' | 'results'
  const [selectedCampaign, setSelectedCampaign] = useState(null)
  const textareaRef = useRef(null)

  const completed = countCompleted(info)
  const isReady = completed >= 3

  // Auto-grow textarea
  const autoGrow = useCallback(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = '52px'
    el.style.height = Math.min(el.scrollHeight, 160) + 'px'
  }, [])

  // Detect info on text change
  useEffect(() => {
    const combined = allText + ' ' + input
    setInfo(detectCampaignInfo(combined))
  }, [input, allText])

  // Handle tag click
  const addTag = (text) => {
    setInput(prev => (prev ? prev + ' ' + text : text))
    textareaRef.current?.focus()
    setTimeout(autoGrow, 0)
  }

  // Handle send (Enter key or button)
  const sendMessage = () => {
    if (!input.trim()) return
    setAllText(prev => (prev ? prev + ' ' : '') + input.trim())
    setInput('')
    setTimeout(autoGrow, 0)
  }

  // Handle submit → transition to results
  const generateCampaigns = () => {
    setPhase('results')
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  // ─── RESULTS VIEW ───
  if (phase === 'results') {
    const userText = allText || input || 'We are a fintech SaaS company targeting B2B enterprise, focused on brand awareness and thought leadership via LinkedIn and Twitter.'

    return (
      <>
        {/* Collapsed input at top */}
        <div className="px-8 py-4 bg-white border-b border-gray-200">
          <div className="flex items-end gap-2 border border-gray-200 rounded-card p-1.5 shadow-card">
            <textarea
              ref={textareaRef}
              className="flex-1 border-none outline-none resize-none text-[15px] text-gray-900 px-4 py-3 bg-transparent min-h-[52px] max-h-[160px] font-sans leading-relaxed"
              placeholder="Refine your campaign..."
              rows={1}
            />
            <button className="w-10 h-10 rounded-[10px] bg-brand grid place-items-center shrink-0 mr-1 mb-1 hover:bg-brand-700 transition-fast">
              <Send size={18} className="text-white" />
            </button>
          </div>
        </div>

        {/* Results body */}
        <div className="flex-1 overflow-y-auto px-8 py-7 custom-scrollbar">
          {/* Chat context */}
          <div className="mb-5 fade-in">
            <div className="flex gap-3 mb-4">
              <div className="w-7 h-7 rounded-lg bg-surface-alt border border-gray-200 grid place-items-center text-[11px] font-bold text-gray-400 shrink-0">E</div>
              <p className="text-sm text-gray-900 leading-relaxed max-w-[560px]">{userText}</p>
            </div>
            <div className="flex gap-3">
              <div className="w-7 h-7 rounded-lg bg-brand grid place-items-center text-[11px] font-bold text-white shrink-0">S</div>
              <p className="text-sm text-gray-500 leading-relaxed max-w-[560px]">
                Based on your profile, I found 3 trending signals with high relevance to your brand. Here are 3 campaign strategies ranked by confidence — each with recommended channels.
              </p>
            </div>
          </div>

          {/* Header */}
          <div className="flex items-center justify-between mb-6 fade-in">
            <h2 className="text-xl font-extrabold text-gray-900 tracking-tight">Proposed Campaigns</h2>
            <span className="inline-flex items-center gap-1.5 px-3 py-[5px] rounded-full text-xs font-semibold bg-emerald-50 text-emerald-600">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 pulse-dot" />
              3 signals matched
            </span>
          </div>

          {/* Campaign cards */}
          <div className="flex flex-col gap-4">
            {MOCK_CAMPAIGNS.map((campaign, i) => (
              <CampaignCard
                key={campaign.id}
                campaign={campaign}
                rank={i + 1}
                selected={selectedCampaign === campaign.id}
                onSelect={setSelectedCampaign}
              />
            ))}
          </div>

          {/* Action bar */}
          <div className="flex items-center justify-between mt-6 pt-5 border-t border-gray-100 fade-in">
            <button
              onClick={() => { setPhase('input'); setSelectedCampaign(null) }}
              className="inline-flex items-center gap-1.5 px-4 py-2.5 rounded-[10px] border border-gray-200 bg-white text-[13px] font-semibold text-gray-500 hover:bg-surface-alt hover:text-gray-900 transition-fast"
            >
              <RotateCcw size={16} />
              Regenerate
            </button>
            <button
              disabled={!selectedCampaign}
              className="px-6 py-2.5 rounded-[10px] bg-brand text-white text-sm font-bold shadow-[0_2px_8px_rgba(0,102,255,0.2)] hover:bg-brand-700 hover:-translate-y-px transition-fast disabled:opacity-40 disabled:cursor-not-allowed disabled:transform-none"
            >
              Continue with selected →
            </button>
          </div>
        </div>
      </>
    )
  }

  // ─── INPUT VIEW (hero state) ───
  return (
    <div className="flex-1 flex flex-col items-center justify-center px-10 transition-layout">
      <h1 className="text-[32px] font-extrabold text-gray-900 tracking-tight mb-1.5 text-center">
        Create your first campaign
      </h1>
      <p className="text-[15px] text-gray-500 text-center mb-8">
        Tell us about your company and goals. We'll match you with trending signals and generate campaigns.
      </p>

      {/* Input box */}
      <div className="w-full max-w-[680px]">
        <div className="bg-white border-[1.5px] border-gray-200 rounded-2xl p-1.5 shadow-card-md input-focus-ring transition-med">
          <div className="flex items-end gap-2">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => { setInput(e.target.value); autoGrow() }}
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

          {/* Tag chips */}
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

      {/* Progress + checklist */}
      <div className="w-full max-w-[680px] mt-6">
        <div className="flex items-center gap-3 mb-4">
          <div className="flex-1 h-1.5 bg-surface-alt rounded-full overflow-hidden">
            <div
              className="h-full rounded-full bg-brand progress-animate"
              style={{ width: `${(completed / 4) * 100}%` }}
            />
          </div>
          <span className="text-xs font-semibold text-gray-400 whitespace-nowrap">
            {completed} / 4 completed
          </span>
        </div>

        <div className="grid grid-cols-2 gap-2">
          <ChecklistItem label="Company or product info" done={info.company} />
          <ChecklistItem label="Target audience" done={info.audience} />
          <ChecklistItem label="Campaign goals" done={info.goal} />
          <ChecklistItem label="Preferred channels" done={info.channel} />
        </div>

        {/* Submit button */}
        <div className={cn(
          'flex justify-center mt-5 transition-all duration-300',
          isReady ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-2 pointer-events-none'
        )}>
          <button
            onClick={generateCampaigns}
            className="px-8 py-3 rounded-[10px] bg-brand text-white text-[15px] font-bold shadow-[0_2px_8px_rgba(0,102,255,0.25)] hover:bg-brand-700 hover:-translate-y-px hover:shadow-[0_4px_16px_rgba(0,102,255,0.3)] transition-fast"
          >
            Generate Campaigns →
          </button>
        </div>
      </div>
    </div>
  )
}

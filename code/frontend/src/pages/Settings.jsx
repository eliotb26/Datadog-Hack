import { useState, useEffect } from 'react'
import axios from 'axios'
import { Save, Globe, Target, Megaphone, Palette, Loader2, RefreshCw } from 'lucide-react'
import { cn } from '@/lib/utils'

const API_BASE = import.meta.env.VITE_API_URL || ''

const TONE_OPTIONS = ['Professional', 'Conversational', 'Bold', 'Technical', 'Playful']
const INDUSTRY_OPTIONS = ['Fintech', 'SaaS', 'Healthcare', 'E-commerce', 'AI/ML', 'Crypto', 'Enterprise', 'Consumer']

export default function Settings() {
  const [saved, setSaved] = useState(false)
  const [saveError, setSaveError] = useState('')
  const [loading, setLoading] = useState(false)
  const [fetchingWebsite, setFetchingWebsite] = useState(false)
  const [form, setForm] = useState({
    companyName: '',
    website: '',
    industry: 'Fintech',
    description: '',
    audience: '',
    tone: 'Professional',
    goals: '',
    avoidTopics: '',
  })

  const update = (key, value) => {
    setForm(prev => ({ ...prev, [key]: value }))
    setSaved(false)
    setSaveError('')
  }

  // Load existing profile on mount
  useEffect(() => {
    axios.get(`${API_BASE}/api/company/profile`).then(res => {
      const p = res.data
      setForm(prev => ({
        ...prev,
        companyName: p.name || prev.companyName,
        website: p.website || prev.website,
        industry: p.industry || prev.industry,
        description: prev.description || '',
        audience: p.target_audience || prev.audience,
        tone: p.tone_of_voice || prev.tone,
        goals: p.campaign_goals || prev.goals,
      }))
    }).catch(() => { /* no profile yet */ })
  }, [])

  const handleSave = async () => {
    setSaveError('')
    setLoading(true)
    try {
      await axios.post(`${API_BASE}/api/company/intake`, {
        companyName: form.companyName || 'My Company',
        website: form.website || null,
        industry: form.industry || 'General',
        description: form.description || null,
        audience: form.audience || null,
        tone: form.tone || null,
        goals: form.goals || null,
        avoidTopics: form.avoidTopics || null,
      })
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } catch (err) {
      setSaveError(err.response?.data?.detail || err.message || 'Failed to save')
    } finally {
      setLoading(false)
    }
  }

  const handleFetchFromWebsite = async () => {
    const url = (form.website || '').trim()
    if (!url) return
    setFetchingWebsite(true)
    setSaveError('')
    try {
      await axios.post(`${API_BASE}/api/company/intake`, {
        companyName: form.companyName || 'From website',
        website: url,
        industry: form.industry || 'General',
        description: null,
        audience: null,
        tone: null,
        goals: null,
        avoidTopics: null,
      })
      const profileRes = await axios.get(`${API_BASE}/api/company/profile`)
      const p = profileRes.data
      setForm(prev => ({
        ...prev,
        companyName: p.name || prev.companyName,
        website: p.website || prev.website,
        industry: p.industry || prev.industry,
        audience: p.target_audience || prev.audience,
        tone: p.tone_of_voice || prev.tone,
        goals: p.campaign_goals || prev.goals,
      }))
      setSaved(true)
      setTimeout(() => setSaved(false), 3000)
    } catch (err) {
      setSaveError(err.response?.data?.detail || err.message || 'Could not fetch or analyze website')
    } finally {
      setFetchingWebsite(false)
    }
  }

  return (
    <div className="flex-1 overflow-y-auto custom-scrollbar">
      <div className="max-w-2xl mx-auto px-8 py-8">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl font-extrabold text-gray-900 tracking-tight">Settings</h1>
            <p className="text-sm text-gray-500 mt-1">Configure your brand profile and preferences.</p>
          </div>
          <button
            onClick={handleSave}
            disabled={loading}
            className={cn(
              'inline-flex items-center gap-2 px-4 py-2.5 rounded-[10px] text-sm font-semibold transition-fast',
              saved
                ? 'bg-emerald-50 text-emerald-600'
                : 'bg-brand text-white hover:bg-brand-700 disabled:opacity-50'
            )}
          >
            {loading ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
            {saved ? 'Saved!' : loading ? 'Saving…' : 'Save Changes'}
          </button>
        </div>
        {saveError && (
          <p className="mb-4 text-sm text-red-600 bg-red-50 px-4 py-2 rounded-lg">{saveError}</p>
        )}

        {/* Brand Profile Section */}
        <section className="mb-8">
          <div className="flex items-center gap-2 mb-4">
            <Globe size={18} className="text-brand" />
            <h2 className="text-base font-bold text-gray-900">Brand Profile</h2>
          </div>
          <div className="bg-white rounded-card border border-gray-200 p-6 space-y-5">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-gray-500 mb-1.5">Company Name</label>
                <input
                  type="text"
                  value={form.companyName}
                  onChange={e => update('companyName', e.target.value)}
                  placeholder="Acme Inc."
                  className="w-full px-3 py-2.5 rounded-lg border border-gray-200 text-sm text-gray-900 placeholder:text-gray-300 outline-none focus:border-brand/40 focus:ring-2 focus:ring-brand/10 transition-fast"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-gray-500 mb-1.5">Website</label>
                <div className="flex gap-2">
                  <input
                    type="url"
                    value={form.website}
                    onChange={e => update('website', e.target.value)}
                    placeholder="https://acme.com"
                    className="flex-1 px-3 py-2.5 rounded-lg border border-gray-200 text-sm text-gray-900 placeholder:text-gray-300 outline-none focus:border-brand/40 focus:ring-2 focus:ring-brand/10 transition-fast"
                  />
                  <button
                    type="button"
                    onClick={handleFetchFromWebsite}
                    disabled={!form.website?.trim() || fetchingWebsite}
                    className="shrink-0 inline-flex items-center gap-1.5 px-3 py-2.5 rounded-lg border border-brand bg-brand/5 text-brand text-xs font-semibold hover:bg-brand/10 disabled:opacity-40 disabled:cursor-not-allowed transition-fast"
                    title="Fetch and analyze this website to pre-fill your profile"
                  >
                    {fetchingWebsite ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
                    {fetchingWebsite ? 'Analyzing…' : 'Fetch from domain'}
                  </button>
                </div>
                <p className="mt-1 text-[11px] text-gray-400">Enter your domain and click to pull company info from your website.</p>
              </div>
            </div>
            <div>
              <label className="block text-xs font-semibold text-gray-500 mb-1.5">Industry</label>
              <div className="flex flex-wrap gap-2">
                {INDUSTRY_OPTIONS.map(ind => (
                  <button
                    key={ind}
                    onClick={() => update('industry', ind)}
                    className={cn(
                      'px-3 py-1.5 rounded-lg text-xs font-semibold border transition-fast',
                      form.industry === ind
                        ? 'border-brand bg-brand-50 text-brand'
                        : 'border-gray-200 text-gray-500 hover:border-gray-300'
                    )}
                  >
                    {ind}
                  </button>
                ))}
              </div>
            </div>
            <div>
              <label className="block text-xs font-semibold text-gray-500 mb-1.5">Company Description</label>
              <textarea
                value={form.description}
                onChange={e => update('description', e.target.value)}
                placeholder="What does your company do? What problem do you solve?"
                rows={3}
                className="w-full px-3 py-2.5 rounded-lg border border-gray-200 text-sm text-gray-900 placeholder:text-gray-300 outline-none focus:border-brand/40 focus:ring-2 focus:ring-brand/10 transition-fast resize-none"
              />
            </div>
          </div>
        </section>

        {/* Target Audience */}
        <section className="mb-8">
          <div className="flex items-center gap-2 mb-4">
            <Target size={18} className="text-teal" />
            <h2 className="text-base font-bold text-gray-900">Target Audience</h2>
          </div>
          <div className="bg-white rounded-card border border-gray-200 p-6">
            <label className="block text-xs font-semibold text-gray-500 mb-1.5">Who are you trying to reach?</label>
            <textarea
              value={form.audience}
              onChange={e => update('audience', e.target.value)}
              placeholder="e.g., B2B enterprise CFOs, Series A startup founders, developer advocates..."
              rows={3}
              className="w-full px-3 py-2.5 rounded-lg border border-gray-200 text-sm text-gray-900 placeholder:text-gray-300 outline-none focus:border-brand/40 focus:ring-2 focus:ring-brand/10 transition-fast resize-none"
            />
          </div>
        </section>

        {/* Brand Voice */}
        <section className="mb-8">
          <div className="flex items-center gap-2 mb-4">
            <Palette size={18} className="text-amber-500" />
            <h2 className="text-base font-bold text-gray-900">Brand Voice</h2>
          </div>
          <div className="bg-white rounded-card border border-gray-200 p-6">
            <label className="block text-xs font-semibold text-gray-500 mb-1.5">Tone</label>
            <div className="flex flex-wrap gap-2 mb-5">
              {TONE_OPTIONS.map(tone => (
                <button
                  key={tone}
                  onClick={() => update('tone', tone)}
                  className={cn(
                    'px-3 py-1.5 rounded-lg text-xs font-semibold border transition-fast',
                    form.tone === tone
                      ? 'border-brand bg-brand-50 text-brand'
                      : 'border-gray-200 text-gray-500 hover:border-gray-300'
                  )}
                >
                  {tone}
                </button>
              ))}
            </div>
            <label className="block text-xs font-semibold text-gray-500 mb-1.5">Topics to Avoid</label>
            <textarea
              value={form.avoidTopics}
              onChange={e => update('avoidTopics', e.target.value)}
              placeholder="e.g., political commentary, competitor mentions..."
              rows={2}
              className="w-full px-3 py-2.5 rounded-lg border border-gray-200 text-sm text-gray-900 placeholder:text-gray-300 outline-none focus:border-brand/40 focus:ring-2 focus:ring-brand/10 transition-fast resize-none"
            />
          </div>
        </section>

        {/* Campaign Goals */}
        <section className="mb-12">
          <div className="flex items-center gap-2 mb-4">
            <Megaphone size={18} className="text-emerald-600" />
            <h2 className="text-base font-bold text-gray-900">Default Campaign Goals</h2>
          </div>
          <div className="bg-white rounded-card border border-gray-200 p-6">
            <label className="block text-xs font-semibold text-gray-500 mb-1.5">What are you typically trying to achieve?</label>
            <textarea
              value={form.goals}
              onChange={e => update('goals', e.target.value)}
              placeholder="e.g., brand awareness, thought leadership, lead generation, product launches..."
              rows={3}
              className="w-full px-3 py-2.5 rounded-lg border border-gray-200 text-sm text-gray-900 placeholder:text-gray-300 outline-none focus:border-brand/40 focus:ring-2 focus:ring-brand/10 transition-fast resize-none"
            />
          </div>
        </section>
      </div>
    </div>
  )
}

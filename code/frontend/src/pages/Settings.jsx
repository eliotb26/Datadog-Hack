import { useState } from 'react'
import { Save, Globe, Target, Megaphone, Palette } from 'lucide-react'
import { cn } from '@/lib/utils'

const TONE_OPTIONS = ['Professional', 'Conversational', 'Bold', 'Technical', 'Playful']
const INDUSTRY_OPTIONS = ['Fintech', 'SaaS', 'Healthcare', 'E-commerce', 'AI/ML', 'Crypto', 'Enterprise', 'Consumer']

export default function Settings() {
  const [saved, setSaved] = useState(false)
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
  }

  const handleSave = () => {
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
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
            className={cn(
              'inline-flex items-center gap-2 px-4 py-2.5 rounded-[10px] text-sm font-semibold transition-fast',
              saved
                ? 'bg-emerald-50 text-emerald-600'
                : 'bg-brand text-white hover:bg-brand-700'
            )}
          >
            <Save size={16} />
            {saved ? 'Saved!' : 'Save Changes'}
          </button>
        </div>

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
                <input
                  type="url"
                  value={form.website}
                  onChange={e => update('website', e.target.value)}
                  placeholder="https://acme.com"
                  className="w-full px-3 py-2.5 rounded-lg border border-gray-200 text-sm text-gray-900 placeholder:text-gray-300 outline-none focus:border-brand/40 focus:ring-2 focus:ring-brand/10 transition-fast"
                />
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

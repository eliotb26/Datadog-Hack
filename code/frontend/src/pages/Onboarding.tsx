import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { createCompany } from '@/lib/api'

export default function Onboarding() {
  const navigate = useNavigate()
  const [loading, setLoading] = useState(false)
  const [formData, setFormData] = useState({
    name: '',
    industry: '',
    tone_of_voice: '',
    target_audience: '',
    campaign_goals: '',
    competitors: '',
    visual_style: '',
  })

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)

    try {
      const data = {
        ...formData,
        competitors: formData.competitors.split(',').map(c => c.trim()).filter(Boolean),
        content_history: [],
        safety_threshold: 0.7,
      }

      await createCompany(data)
      alert('Company profile created successfully!')
      navigate('/')
    } catch (error) {
      console.error('Failed to create company:', error)
      alert('Failed to create company profile')
    } finally {
      setLoading(false)
    }
  }

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    setFormData(prev => ({
      ...prev,
      [e.target.name]: e.target.value,
    }))
  }

  return (
    <div className="max-w-2xl mx-auto">
      <div className="mb-8">
        <h1 className="text-4xl font-bold text-white mb-3">
          Brand Onboarding
        </h1>
        <p className="text-gray-400 text-lg">Configure your brand profile for AI-powered ad generation</p>
      </div>

      <form onSubmit={handleSubmit} className="glass-card rounded-lg p-8 space-y-6">
        <div>
          <label className="block text-sm font-semibold text-gray-300 mb-2">
            Brand Name *
          </label>
          <input
            type="text"
            name="name"
            required
            value={formData.name}
            onChange={handleChange}
            className="w-full px-4 py-3 glass rounded-lg text-white placeholder-gray-500 focus:ring-2 focus:ring-emerald-500 focus:outline-none transition-all"
            placeholder="Enter brand name"
          />
        </div>

        <div>
          <label className="block text-sm font-semibold text-gray-300 mb-2">
            Industry *
          </label>
          <input
            type="text"
            name="industry"
            required
            value={formData.industry}
            onChange={handleChange}
            className="w-full px-4 py-3 glass rounded-lg text-white placeholder-gray-500 focus:ring-2 focus:ring-emerald-500 focus:outline-none transition-all"
            placeholder="e.g., fintech, e-commerce, SaaS"
          />
        </div>

        <div>
          <label className="block text-sm font-semibold text-gray-300 mb-2">
            Tone of Voice
          </label>
          <input
            type="text"
            name="tone_of_voice"
            value={formData.tone_of_voice}
            onChange={handleChange}
            className="w-full px-4 py-3 glass rounded-lg text-white placeholder-gray-500 focus:ring-2 focus:ring-emerald-500 focus:outline-none transition-all"
            placeholder="e.g., professional, casual, bold"
          />
        </div>

        <div>
          <label className="block text-sm font-semibold text-gray-300 mb-2">
            Target Audience
          </label>
          <textarea
            name="target_audience"
            value={formData.target_audience}
            onChange={handleChange}
            rows={3}
            className="w-full px-4 py-3 glass rounded-lg text-white placeholder-gray-500 focus:ring-2 focus:ring-emerald-500 focus:outline-none transition-all"
            placeholder="Describe your target audience"
          />
        </div>

        <div>
          <label className="block text-sm font-semibold text-gray-300 mb-2">
            Campaign Goals
          </label>
          <textarea
            name="campaign_goals"
            value={formData.campaign_goals}
            onChange={handleChange}
            rows={3}
            className="w-full px-4 py-3 glass rounded-lg text-white placeholder-gray-500 focus:ring-2 focus:ring-emerald-500 focus:outline-none transition-all"
            placeholder="What do you want to achieve?"
          />
        </div>

        <div>
          <label className="block text-sm font-semibold text-gray-300 mb-2">
            Competitors (comma-separated)
          </label>
          <input
            type="text"
            name="competitors"
            value={formData.competitors}
            onChange={handleChange}
            className="w-full px-4 py-3 glass rounded-lg text-white placeholder-gray-500 focus:ring-2 focus:ring-emerald-500 focus:outline-none transition-all"
            placeholder="Competitor A, Competitor B"
          />
        </div>

        <div>
          <label className="block text-sm font-semibold text-gray-300 mb-2">
            Visual Style
          </label>
          <input
            type="text"
            name="visual_style"
            value={formData.visual_style}
            onChange={handleChange}
            className="w-full px-4 py-3 glass rounded-lg text-white placeholder-gray-500 focus:ring-2 focus:ring-emerald-500 focus:outline-none transition-all"
            placeholder="e.g., minimalist, bold, modern"
          />
        </div>

        <div className="flex gap-4 pt-4">
          <button
            type="button"
            onClick={() => navigate('/')}
            className="flex-1 px-6 py-4 glass rounded-lg text-gray-300 hover:bg-white/10 font-semibold transition-all"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={loading}
            className="flex-1 px-6 py-4 bg-emerald-500 text-white rounded-lg hover:bg-emerald-600 disabled:opacity-50 font-semibold transition-all"
          >
            {loading ? 'Creating...' : 'Create Profile'}
          </button>
        </div>
      </form>
    </div>
  )
}

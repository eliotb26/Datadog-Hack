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
        <h1 className="text-4xl font-black text-transparent bg-clip-text bg-gradient-to-r from-purple-600 to-pink-600">
          Let's Get Your Brand Viral! 🚀
        </h1>
        <p className="text-gray-600 mt-3 text-lg font-semibold">Tell us about your brand and we'll cook up some fire ads 🔥</p>
      </div>

      <form onSubmit={handleSubmit} className="bg-white rounded-2xl border-2 border-purple-200 p-8 space-y-6 shadow-xl">
        <div>
          <label className="block text-sm font-bold text-gray-700 mb-2">
            Brand Name 🏢 *
          </label>
          <input
            type="text"
            name="name"
            required
            value={formData.name}
            onChange={handleChange}
            className="w-full px-4 py-3 border-2 border-purple-200 rounded-xl focus:ring-2 focus:ring-purple-500 focus:border-transparent font-semibold"
            placeholder="e.g., Cool Sneakers Co."
          />
        </div>

        <div>
          <label className="block text-sm font-bold text-gray-700 mb-2">
            Industry 🏭 *
          </label>
          <input
            type="text"
            name="industry"
            required
            value={formData.industry}
            onChange={handleChange}
            className="w-full px-4 py-3 border-2 border-purple-200 rounded-xl focus:ring-2 focus:ring-purple-500 focus:border-transparent font-semibold"
            placeholder="e.g., fashion, tech, food, gaming"
          />
        </div>

        <div>
          <label className="block text-sm font-bold text-gray-700 mb-2">
            Brand Vibe 😎
          </label>
          <input
            type="text"
            name="tone_of_voice"
            value={formData.tone_of_voice}
            onChange={handleChange}
            className="w-full px-4 py-3 border-2 border-purple-200 rounded-xl focus:ring-2 focus:ring-purple-500 focus:border-transparent font-semibold"
            placeholder="e.g., edgy and bold, fun and quirky, professional"
          />
        </div>

        <div>
          <label className="block text-sm font-bold text-gray-700 mb-2">
            Who's Your Crowd? 👥
          </label>
          <textarea
            name="target_audience"
            value={formData.target_audience}
            onChange={handleChange}
            rows={3}
            className="w-full px-4 py-3 border-2 border-purple-200 rounded-xl focus:ring-2 focus:ring-purple-500 focus:border-transparent font-semibold"
            placeholder="e.g., Gen Z sneakerheads, tech-savvy millennials"
          />
        </div>

        <div>
          <label className="block text-sm font-bold text-gray-700 mb-2">
            What's The Goal? 🎯
          </label>
          <textarea
            name="campaign_goals"
            value={formData.campaign_goals}
            onChange={handleChange}
            rows={3}
            className="w-full px-4 py-3 border-2 border-purple-200 rounded-xl focus:ring-2 focus:ring-purple-500 focus:border-transparent font-semibold"
            placeholder="e.g., go viral on TikTok, boost sales, build hype"
          />
        </div>

        <div>
          <label className="block text-sm font-bold text-gray-700 mb-2">
            Who Are You Competing With? 🥊 (comma-separated)
          </label>
          <input
            type="text"
            name="competitors"
            value={formData.competitors}
            onChange={handleChange}
            className="w-full px-4 py-3 border-2 border-purple-200 rounded-xl focus:ring-2 focus:ring-purple-500 focus:border-transparent font-semibold"
            placeholder="e.g., Nike, Adidas, Puma"
          />
        </div>

        <div>
          <label className="block text-sm font-bold text-gray-700 mb-2">
            Visual Style 🎨
          </label>
          <input
            type="text"
            name="visual_style"
            value={formData.visual_style}
            onChange={handleChange}
            className="w-full px-4 py-3 border-2 border-purple-200 rounded-xl focus:ring-2 focus:ring-purple-500 focus:border-transparent font-semibold"
            placeholder="e.g., neon colors, minimalist, retro 90s"
          />
        </div>

        <div className="flex gap-4 pt-4">
          <button
            type="button"
            onClick={() => navigate('/')}
            className="flex-1 px-6 py-4 border-2 border-gray-300 text-gray-700 rounded-xl hover:bg-gray-50 font-bold transition-all"
          >
            Nah, Go Back
          </button>
          <button
            type="submit"
            disabled={loading}
            className="flex-1 px-6 py-4 bg-gradient-to-r from-purple-600 to-pink-600 text-white rounded-xl hover:shadow-xl disabled:opacity-50 font-bold transform hover:scale-105 transition-all"
          >
            {loading ? 'Creating Magic... ✨' : "Let's Go! 🚀"}
          </button>
        </div>
      </form>
    </div>
  )
}

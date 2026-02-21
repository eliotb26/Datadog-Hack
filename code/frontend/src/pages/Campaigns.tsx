import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Plus } from 'lucide-react'
import { getCampaigns, getCompanies, getSignals, generateCampaigns } from '@/lib/api'
import type { Campaign, CompanyProfile, TrendSignal } from '@/lib/types'
import CampaignCard from '@/components/CampaignCard'

export default function Campaigns() {
  const navigate = useNavigate()
  const [campaigns, setCampaigns] = useState<Campaign[]>([])
  const [companies, setCompanies] = useState<CompanyProfile[]>([])
  const [signals, setSignals] = useState<TrendSignal[]>([])
  const [loading, setLoading] = useState(true)
  const [generating, setGenerating] = useState(false)
  const [showGenerateModal, setShowGenerateModal] = useState(false)
  const [selectedCompany, setSelectedCompany] = useState('')
  const [selectedSignal, setSelectedSignal] = useState('')

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    try {
      const [campaignsRes, companiesRes, signalsRes] = await Promise.all([
        getCampaigns(),
        getCompanies(),
        getSignals(),
      ])
      setCampaigns(campaignsRes.data)
      setCompanies(companiesRes.data)
      setSignals(signalsRes.data)
    } catch (error) {
      console.error('Failed to load data:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleGenerate = async () => {
    if (!selectedCompany || !selectedSignal) {
      alert('Please select both company and signal')
      return
    }

    setGenerating(true)
    try {
      await generateCampaigns({
        company_id: selectedCompany,
        signal_id: selectedSignal,
        num_concepts: 3,
      })
      setShowGenerateModal(false)
      await loadData()
      alert('Campaigns generated successfully!')
    } catch (error) {
      console.error('Failed to generate campaigns:', error)
      alert('Failed to generate campaigns')
    } finally {
      setGenerating(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-400">Loading campaigns...</div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-4xl font-bold text-white mb-2">
            Campaigns
          </h1>
          <p className="text-gray-400">AI-generated ad content</p>
        </div>
        <button
          onClick={() => setShowGenerateModal(true)}
          className="flex items-center px-6 py-3 bg-emerald-500 text-white rounded-lg hover:bg-emerald-600 font-semibold transition-colors"
        >
          <Plus className="w-5 h-5 mr-2" />
          Generate Campaigns
        </button>
      </div>

      {/* Campaigns Grid */}
      {campaigns.length === 0 ? (
        <div className="glass-card rounded-lg p-12 text-center">
          <p className="text-gray-400 text-lg mb-4">No campaigns yet. Generate your first campaign.</p>
          <button
            onClick={() => setShowGenerateModal(true)}
            className="px-8 py-4 bg-emerald-500 text-white rounded-lg hover:bg-emerald-600 font-semibold transition-colors"
          >
            Generate Campaigns
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {campaigns.map((campaign) => (
            <CampaignCard
              key={campaign.id}
              campaign={campaign}
              onClick={() => navigate(`/campaigns/${campaign.id}`)}
            />
          ))}
        </div>
      )}

      {/* Generate Modal */}
      {showGenerateModal && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 backdrop-blur-sm">
          <div className="glass-strong rounded-lg p-8 max-w-md w-full mx-4">
            <h2 className="text-2xl font-bold text-white mb-6">
              Generate Campaigns
            </h2>

            <div className="space-y-4 mb-6">
              <div>
                <label className="block text-sm font-semibold text-gray-300 mb-2">
                  Select Brand
                </label>
                <select
                  value={selectedCompany}
                  onChange={(e) => setSelectedCompany(e.target.value)}
                  className="w-full px-4 py-3 glass rounded-lg text-white focus:ring-2 focus:ring-emerald-500 focus:outline-none"
                >
                  <option value="">Choose a brand...</option>
                  {companies.map((company) => (
                    <option key={company.id} value={company.id}>
                      {company.name}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-semibold text-gray-300 mb-2">
                  Select Trend Signal
                </label>
                <select
                  value={selectedSignal}
                  onChange={(e) => setSelectedSignal(e.target.value)}
                  className="w-full px-4 py-3 glass rounded-lg text-white focus:ring-2 focus:ring-emerald-500 focus:outline-none"
                >
                  <option value="">Choose a signal...</option>
                  {signals.map((signal) => (
                    <option key={signal.id} value={signal.id}>
                      {signal.title}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="flex gap-4">
              <button
                onClick={() => setShowGenerateModal(false)}
                className="flex-1 px-4 py-3 glass rounded-lg text-gray-300 hover:bg-white/10 font-semibold transition-all"
              >
                Cancel
              </button>
              <button
                onClick={handleGenerate}
                disabled={generating}
                className="flex-1 px-4 py-3 bg-emerald-500 text-white rounded-lg hover:bg-emerald-600 disabled:opacity-50 font-semibold transition-all"
              >
                {generating ? 'Generating...' : 'Generate'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

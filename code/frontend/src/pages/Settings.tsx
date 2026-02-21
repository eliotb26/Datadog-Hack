import { useEffect, useState } from 'react'
import { getCompanies } from '@/lib/api'
import type { CompanyProfile } from '@/lib/types'
import { formatDate } from '@/lib/utils'

export default function Settings() {
  const [companies, setCompanies] = useState<CompanyProfile[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadCompanies()
  }, [])

  const loadCompanies = async () => {
    try {
      const res = await getCompanies()
      setCompanies(res.data)
    } catch (error) {
      console.error('Failed to load companies:', error)
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-500">Loading settings...</div>
      </div>
    )
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Settings</h1>
        <p className="text-gray-600 mt-1">Manage company profiles and system configuration</p>
      </div>

      {/* Company Profiles */}
      <div className="bg-white rounded-lg border border-gray-200">
        <div className="p-6 border-b border-gray-200">
          <h2 className="text-xl font-semibold text-gray-900">Company Profiles</h2>
        </div>
        <div className="divide-y divide-gray-200">
          {companies.length === 0 ? (
            <div className="p-12 text-center text-gray-500">
              No companies yet. Create one from the onboarding page.
            </div>
          ) : (
            companies.map((company) => (
              <div key={company.id} className="p-6">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <h3 className="text-lg font-semibold text-gray-900">{company.name}</h3>
                    <p className="text-sm text-gray-600 mt-1">{company.industry}</p>
                    {company.tone_of_voice && (
                      <p className="text-sm text-gray-600 mt-2">
                        <span className="font-medium">Tone:</span> {company.tone_of_voice}
                      </p>
                    )}
                    {company.target_audience && (
                      <p className="text-sm text-gray-600 mt-1">
                        <span className="font-medium">Audience:</span> {company.target_audience}
                      </p>
                    )}
                    {company.competitors.length > 0 && (
                      <p className="text-sm text-gray-600 mt-1">
                        <span className="font-medium">Competitors:</span> {company.competitors.join(', ')}
                      </p>
                    )}
                    <p className="text-xs text-gray-500 mt-3">
                      Created {formatDate(company.created_at)}
                    </p>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* System Info */}
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h2 className="text-xl font-semibold text-gray-900 mb-4">System Information</h2>
        <div className="space-y-2 text-sm">
          <div className="flex justify-between">
            <span className="text-gray-600">Platform:</span>
            <span className="font-medium text-gray-900">SIGNAL v0.1.0</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-600">Backend:</span>
            <span className="font-medium text-gray-900">FastAPI + Python</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-600">Frontend:</span>
            <span className="font-medium text-gray-900">React + Vite</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-600">AI Framework:</span>
            <span className="font-medium text-gray-900">Google DeepMind ADK</span>
          </div>
        </div>
      </div>
    </div>
  )
}

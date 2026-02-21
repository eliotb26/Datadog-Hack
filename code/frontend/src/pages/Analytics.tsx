import { useEffect, useState } from 'react'
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import { getLearningCurve, getCalibration } from '@/lib/api'

export default function Analytics() {
  const [learningData, setLearningData] = useState<any[]>([])
  const [calibrationData, setCalibrationData] = useState<any[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadAnalytics()
  }, [])

  const loadAnalytics = async () => {
    try {
      const [learningRes, calibrationRes] = await Promise.all([
        getLearningCurve().catch(() => ({ data: [] })),
        getCalibration().catch(() => ({ data: [] })),
      ])
      setLearningData(learningRes.data)
      setCalibrationData(calibrationRes.data)
    } catch (error) {
      console.error('Failed to load analytics:', error)
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-500">Loading analytics...</div>
      </div>
    )
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-4xl font-bold text-white mb-2">
          Analytics
        </h1>
        <p className="text-gray-400 text-lg">System performance and learning metrics</p>
      </div>

      {/* Learning Curve */}
      <div className="glass-card rounded-lg p-6">
        <h2 className="text-2xl font-semibold text-white mb-6">Agent Learning Curve</h2>
        {learningData.length > 0 ? (
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={learningData}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
              <XAxis dataKey="date" stroke="#9ca3af" />
              <YAxis stroke="#9ca3af" />
              <Tooltip contentStyle={{ backgroundColor: 'rgba(15, 23, 42, 0.9)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px' }} />
              <Legend />
              <Line type="monotone" dataKey="quality_score" stroke="#10b981" strokeWidth={3} name="Quality Score" />
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <div className="h-64 flex items-center justify-center glass rounded-lg">
            <p className="text-gray-400 text-center px-8">
              No learning data available yet. Generate campaigns to see improvement over time.
            </p>
          </div>
        )}
      </div>

      {/* Signal Calibration */}
      <div className="glass-card rounded-lg p-6">
        <h2 className="text-2xl font-semibold text-white mb-6">Polymarket Signal Calibration</h2>
        {calibrationData.length > 0 ? (
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={calibrationData}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
              <XAxis dataKey="category" stroke="#9ca3af" />
              <YAxis stroke="#9ca3af" />
              <Tooltip contentStyle={{ backgroundColor: 'rgba(15, 23, 42, 0.9)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px' }} />
              <Legend />
              <Bar dataKey="predicted_engagement" fill="#10b981" name="Predicted" />
              <Bar dataKey="actual_engagement" fill="#3b82f6" name="Actual" />
            </BarChart>
          </ResponsiveContainer>
        ) : (
          <div className="h-64 flex items-center justify-center glass rounded-lg">
            <p className="text-gray-400 text-center px-8">
              No calibration data available yet. Post campaigns and track metrics to see signal accuracy.
            </p>
          </div>
        )}
      </div>

      {/* Three Loops Diagram */}
      <div className="glass-card rounded-lg p-6">
        <h2 className="text-2xl font-semibold text-white mb-6">Self-Improving Loops</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="glass-strong rounded-lg p-6 border border-emerald-500/30">
            <h3 className="font-semibold text-emerald-400 text-lg mb-3">Loop 1: Performance</h3>
            <p className="text-sm text-gray-400">
              Tracks engagement metrics and updates content generation prompts based on what works.
            </p>
          </div>
          <div className="glass-strong rounded-lg p-6 border border-blue-500/30">
            <h3 className="font-semibold text-blue-400 text-lg mb-3">Loop 2: Cross-Company</h3>
            <p className="text-sm text-gray-400">
              Anonymized patterns from all companies feed into shared knowledge layer.
            </p>
          </div>
          <div className="glass-strong rounded-lg p-6 border border-purple-500/30">
            <h3 className="font-semibold text-purple-400 text-lg mb-3">Loop 3: Calibration</h3>
            <p className="text-sm text-gray-400">
              Learns which Polymarket signals actually predict content virality.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}

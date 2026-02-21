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
        <h1 className="text-4xl font-black text-transparent bg-clip-text bg-gradient-to-r from-purple-600 to-pink-600">
          Analytics 📊
        </h1>
        <p className="text-gray-600 mt-2 font-semibold text-lg">Watch your AI get smarter in real-time 🧠✨</p>
      </div>

      {/* Learning Curve */}
      <div className="bg-white rounded-2xl border-2 border-purple-200 p-6 shadow-xl">
        <h2 className="text-2xl font-black text-gray-900 mb-6">🚀 AI Learning Curve</h2>
        {learningData.length > 0 ? (
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={learningData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="date" />
              <YAxis />
              <Tooltip />
              <Legend />
              <Line type="monotone" dataKey="quality_score" stroke="#9333ea" strokeWidth={3} name="Quality Score 🎯" />
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <div className="h-64 flex items-center justify-center bg-gradient-to-br from-purple-50 to-pink-50 rounded-xl">
            <p className="text-gray-600 font-bold text-center px-8">
              No learning data yet! Generate some ads to see your AI level up 📈
            </p>
          </div>
        )}
      </div>

      {/* Signal Calibration */}
      <div className="bg-white rounded-2xl border-2 border-pink-200 p-6 shadow-xl">
        <h2 className="text-2xl font-black text-gray-900 mb-6">🎯 Trend Prediction Accuracy</h2>
        {calibrationData.length > 0 ? (
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={calibrationData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="category" />
              <YAxis />
              <Tooltip />
              <Legend />
              <Bar dataKey="predicted_engagement" fill="#9333ea" name="Predicted 🔮" />
              <Bar dataKey="actual_engagement" fill="#ec4899" name="Actual 💯" />
            </BarChart>
          </ResponsiveContainer>
        ) : (
          <div className="h-64 flex items-center justify-center bg-gradient-to-br from-pink-50 to-orange-50 rounded-xl">
            <p className="text-gray-600 font-bold text-center px-8">
              No calibration data yet! Post some ads and track metrics to see how accurate we are 🎲
            </p>
          </div>
        )}
      </div>

      {/* Three Loops Diagram */}
      <div className="bg-white rounded-2xl border-2 border-orange-200 p-6 shadow-xl">
        <h2 className="text-2xl font-black text-gray-900 mb-6">🔄 Self-Improving Magic Loops</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="p-6 bg-gradient-to-br from-blue-500 to-blue-600 rounded-xl text-white shadow-lg transform hover:scale-105 transition-all">
            <h3 className="font-black text-xl mb-3">Loop 1: Performance 📈</h3>
            <p className="text-sm font-semibold opacity-90">
              Tracks what works and updates prompts. Your AI learns from every ad! 🎯
            </p>
          </div>
          <div className="p-6 bg-gradient-to-br from-green-500 to-green-600 rounded-xl text-white shadow-lg transform hover:scale-105 transition-all">
            <h3 className="font-black text-xl mb-3">Loop 2: Cross-Brand 🤝</h3>
            <p className="text-sm font-semibold opacity-90">
              Learns from all brands anonymously. Everyone gets smarter together! 🧠
            </p>
          </div>
          <div className="p-6 bg-gradient-to-br from-purple-500 to-purple-600 rounded-xl text-white shadow-lg transform hover:scale-105 transition-all">
            <h3 className="font-black text-xl mb-3">Loop 3: Trend Calibration 🎲</h3>
            <p className="text-sm font-semibold opacity-90">
              Learns which trends actually go viral. No more guessing! 🔥
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}

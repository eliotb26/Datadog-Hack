import axios from 'axios'
import type { CompanyProfile, TrendSignal, Campaign, CampaignMetrics } from './types'

const api = axios.create({
  baseURL: '/api/v1',
  headers: {
    'Content-Type': 'application/json',
  },
})

// Companies
export const getCompanies = () => api.get<CompanyProfile[]>('/companies')
export const getCompany = (id: string) => api.get<CompanyProfile>(`/companies/${id}`)
export const createCompany = (data: Partial<CompanyProfile>) => api.post<CompanyProfile>('/companies', data)
export const updateCompany = (id: string, data: Partial<CompanyProfile>) => api.put<CompanyProfile>(`/companies/${id}`, data)

// Signals
export const getSignals = () => api.get<TrendSignal[]>('/signals')
export const getSignal = (id: string) => api.get<TrendSignal>(`/signals/${id}`)
export const refreshSignals = () => api.post('/signals/refresh')

// Campaigns
export const getCampaigns = (params?: { company_id?: string; status?: string }) => 
  api.get<Campaign[]>('/campaigns', { params })
export const getCampaign = (id: string) => api.get<Campaign>(`/campaigns/${id}`)
export const generateCampaigns = (data: { company_id: string; signal_id: string; num_concepts?: number }) =>
  api.post<{ concepts: Campaign[] }>('/campaigns/generate', data)
export const approveCampaign = (id: string) => api.post(`/campaigns/${id}/approve`)
export const submitCampaignMetrics = (id: string, metrics: CampaignMetrics) =>
  api.post(`/campaigns/${id}/metrics`, metrics)

// Analytics
export const getLearningCurve = () => api.get('/analytics/learning-curve')
export const getCalibration = () => api.get('/analytics/calibration')
export const getPatterns = () => api.get('/analytics/patterns')
export const triggerFeedback = () => api.post('/feedback/trigger')

// System
export const getHealth = () => api.get('/health')
export const getAgentStatus = () => api.get('/agents/status')

export default api

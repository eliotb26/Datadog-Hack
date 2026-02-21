import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Layout from '@/components/Layout'
import Landing from '@/pages/Landing'
import Dashboard from '@/pages/Dashboard'
import Generate from '@/pages/Generate'
import Campaigns from '@/pages/Campaigns'
import ContentStudio from '@/pages/ContentStudio'
import Trending from '@/pages/Trending'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/app" element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="generate" element={<Generate />} />
          <Route path="campaigns" element={<Campaigns />} />
          <Route path="content" element={<ContentStudio />} />
          <Route path="trending" element={<Trending />} />
        </Route>
        <Route path="/generate" element={<Navigate to="/app/generate" replace />} />
        <Route path="/campaigns" element={<Navigate to="/app/campaigns" replace />} />
        <Route path="/content" element={<Navigate to="/app/content" replace />} />
        <Route path="/trending" element={<Navigate to="/app/trending" replace />} />
      </Routes>
    </BrowserRouter>
  )
}

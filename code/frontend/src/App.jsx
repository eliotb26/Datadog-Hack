import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Layout from '@/components/Layout'
import Landing from '@/pages/Landing'
import Generate from '@/pages/Generate'
import Campaigns from '@/pages/Campaigns'
import ContentStudio from '@/pages/ContentStudio'
import Trending from '@/pages/Trending'
import Settings from '@/pages/Settings'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/app" element={<Layout />}>
          <Route index element={<Generate />} />
          <Route path="campaigns" element={<Campaigns />} />
          <Route path="content" element={<ContentStudio />} />
          <Route path="trending" element={<Trending />} />
          <Route path="settings" element={<Settings />} />
        </Route>
        <Route path="/campaigns" element={<Navigate to="/app/campaigns" replace />} />
        <Route path="/content" element={<Navigate to="/app/content" replace />} />
        <Route path="/trending" element={<Navigate to="/app/trending" replace />} />
        <Route path="/settings" element={<Navigate to="/app/settings" replace />} />
      </Routes>
    </BrowserRouter>
  )
}

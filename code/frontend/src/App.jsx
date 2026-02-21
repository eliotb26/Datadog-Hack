import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout from '@/components/Layout'
import Generate from '@/pages/Generate'
import Campaigns from '@/pages/Campaigns'
import Trending from '@/pages/Trending'
import Settings from '@/pages/Settings'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<Generate />} />
          <Route path="/campaigns" element={<Campaigns />} />
          <Route path="/trending" element={<Trending />} />
          <Route path="/settings" element={<Settings />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

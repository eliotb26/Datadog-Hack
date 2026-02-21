import { Outlet } from 'react-router-dom'
import Sidebar from './Sidebar'

export default function Layout() {
  return (
    <div className="grid grid-cols-[220px_1fr] h-screen">
      <Sidebar />
      <main className="flex flex-col h-screen overflow-hidden bg-bg">
        <Outlet />
      </main>
    </div>
  )
}

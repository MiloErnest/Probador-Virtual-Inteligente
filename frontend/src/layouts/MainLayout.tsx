import { Outlet } from 'react-router-dom'

import Navbar from '@/components/Navbar'

export default function MainLayout() {
  return (
    <div className="flex min-h-dvh flex-col">
      <Navbar />

      <main className="container-page flex-1 py-10 sm:py-14">
        <Outlet />
      </main>

      <footer className="border-t border-black/[0.07]">
        <div className="container-page flex flex-col gap-2 py-6 text-xs text-ink-muted sm:flex-row sm:items-center sm:justify-between">
          <p>Probador Virtual Inteligente · Proyecto universitario</p>
          <p>Fase 1 — Probador virtual</p>
        </div>
      </footer>
    </div>
  )
}

import { Outlet, useLocation } from 'react-router-dom'

import Navbar from '@/components/Navbar'

export default function MainLayout() {
  const { pathname } = useLocation()

  return (
    <div className="flex min-h-dvh flex-col bg-paper">
      <Navbar />

      <main
        key={pathname}
        className="flex-1 animate-entrar pb-20 pt-10 sm:pt-16"
      >
        <Outlet />
      </main>

      <footer className="sobre-negro mt-auto bg-ink text-paper">
        <div className="wrap flex flex-col gap-6 py-10 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="font-display text-2xl leading-none">Probador Virtual</p>
            <p className="mt-2 max-w-sm text-sm leading-relaxed text-paper/50">
              Proyecto universitario. Las telas se prueban en este servidor. Para el
              probador, tu foto se envía a un modelo abierto en Hugging Face, y del resultado
              solo se toma la prenda.
            </p>
          </div>
          <p className="text-[11px] uppercase tracking-rotulo text-paper/40">
            Vestidor inteligente
          </p>
        </div>
      </footer>
    </div>
  )
}

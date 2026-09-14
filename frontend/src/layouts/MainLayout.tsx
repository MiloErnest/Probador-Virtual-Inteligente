import { Outlet, useLocation } from 'react-router-dom'

import Navbar from '@/components/Navbar'

export default function MainLayout() {
  const { pathname } = useLocation()

  // El probador ocupa la pantalla entera y trae su propio ritmo: el relleno
  // generoso del resto de páginas ahí solo estorba.
  const aBordePagina = pathname === '/probador'

  return (
    <div className="flex min-h-dvh flex-col bg-paper">
      <Navbar />

      <main
        key={pathname}
        className={`flex-1 animate-entrar ${aBordePagina ? 'pb-16 pt-6 sm:pt-8' : 'pb-20 pt-10 sm:pt-16'}`}
      >
        <Outlet />
      </main>

      <footer className="sobre-negro mt-auto bg-ink text-paper">
        <div className="wrap flex flex-col gap-6 py-10 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="font-display text-2xl leading-none">Probador Virtual</p>
            <p className="mt-2 max-w-sm text-sm leading-relaxed text-paper/50">
              Proyecto universitario. La detección del cuerpo corre en tu navegador; tu cámara
              no sale de tu equipo.
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

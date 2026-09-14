import { useEffect, useState } from 'react'
import { NavLink, useLocation, useNavigate } from 'react-router-dom'

import { useAuth } from '@/auth/AuthContext'
import HealthBadge from '@/components/HealthBadge'
import { NAV_ITEMS } from '@/navigation'

export default function Navbar() {
  const [abierto, setAbierto] = useState(false)
  const { user, isAuthenticated, logout } = useAuth()
  const navigate = useNavigate()
  const { pathname } = useLocation()

  // Las secciones que exigen cuenta no se enseñan a quien no ha entrado:
  // llevarían a una redirección inmediata al formulario de acceso.
  const visibles = NAV_ITEMS.filter((item) => !item.requiresAuth || isAuthenticated)

  // El menú móvil se cierra al navegar. Sin esto, tocar un enlace cambia la
  // página por debajo y deja la cortina puesta.
  useEffect(() => setAbierto(false), [pathname])

  // Con el menú desplegado, la página de detrás no debe poder desplazarse.
  useEffect(() => {
    document.body.style.overflow = abierto ? 'hidden' : ''
    return () => {
      document.body.style.overflow = ''
    }
  }, [abierto])

  function salir() {
    logout()
    setAbierto(false)
    navigate('/', { replace: true })
  }

  return (
    <header className="sticky top-0 z-40 border-b border-ink-10 bg-paper/90 backdrop-blur-md">
      <div className="wrap flex h-16 items-center justify-between gap-4 sm:h-[72px]">
        <NavLink to="/" className="group flex items-baseline gap-2" aria-label="Inicio">
          <span className="font-display text-xl leading-none tracking-tight sm:text-[22px]">
            Probador
          </span>
          <span className="hidden text-[10px] uppercase tracking-rotulo text-ink-40 transition group-hover:text-ink sm:inline">
            Virtual
          </span>
        </NavLink>

        <nav className="hidden items-center gap-8 md:flex" aria-label="Principal">
          {visibles.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              className={({ isActive }) =>
                `relative py-1 text-sm transition-colors ${
                  isActive ? 'text-ink' : 'text-ink-60 hover:text-ink'
                }`
              }
            >
              {({ isActive }) => (
                <>
                  {item.label}
                  {/* La línea activa se dibuja siempre y se revela con una
                      escala: así entra deslizándose en vez de aparecer. */}
                  <span
                    aria-hidden
                    className={`absolute -bottom-0.5 left-0 h-px w-full origin-left bg-ink transition-transform duration-300 ${
                      isActive ? 'scale-x-100' : 'scale-x-0'
                    }`}
                  />
                </>
              )}
            </NavLink>
          ))}
        </nav>

        <div className="flex items-center gap-2 sm:gap-3">
          <HealthBadge />

          {isAuthenticated ? (
            <button type="button" className="btn-ghost hidden px-4 py-1.5 md:inline-flex" onClick={salir}>
              Salir
            </button>
          ) : (
            <NavLink to="/entrar" className="btn-primary hidden px-4 py-1.5 md:inline-flex">
              Entrar
            </NavLink>
          )}

          <button
            type="button"
            className="-mr-1 flex h-10 w-10 items-center justify-center md:hidden"
            aria-expanded={abierto}
            aria-controls="menu-movil"
            aria-label={abierto ? 'Cerrar menú' : 'Abrir menú'}
            onClick={() => setAbierto((v) => !v)}
          >
            {/* Dos trazos que se cruzan al abrir. Menos ruido que un icono
                importado y se anima solo. */}
            <span className="relative block h-3.5 w-5">
              <span
                className={`absolute left-0 block h-px w-full bg-ink transition-all duration-300 ${
                  abierto ? 'top-1.5 rotate-45' : 'top-0'
                }`}
              />
              <span
                className={`absolute left-0 block h-px w-full bg-ink transition-all duration-300 ${
                  abierto ? 'top-1.5 -rotate-45' : 'top-3'
                }`}
              />
            </span>
          </button>
        </div>
      </div>

      {/* Menú móvil a pantalla completa. Una lista desplegable de 4 elementos
          en un móvil queda apretada contra el borde superior; ocupando la
          pantalla, cada destino es un objetivo grande y legible. */}
      <div
        id="menu-movil"
        className={`fixed inset-x-0 top-16 z-40 h-[calc(100dvh-4rem)] border-t border-ink-10 bg-paper transition-all duration-300 md:hidden ${
          abierto ? 'translate-y-0 opacity-100' : 'pointer-events-none -translate-y-2 opacity-0'
        }`}
      >
        <nav className="wrap flex h-full flex-col pt-6" aria-label="Principal (móvil)">
          {visibles.map((item, indice) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              className={({ isActive }) =>
                `flex items-baseline gap-4 border-b border-ink-10 py-5 font-display text-3xl transition ${
                  isActive ? 'text-ink' : 'text-ink-40'
                }`
              }
            >
              <span className="font-sans text-[11px] tabular-nums text-ink-40">
                {String(indice + 1).padStart(2, '0')}
              </span>
              {item.label}
            </NavLink>
          ))}

          <div className="mt-auto pb-10 pt-8">
            {isAuthenticated ? (
              <div className="flex items-center justify-between gap-4">
                <span className="min-w-0 truncate text-sm text-ink-60">{user?.email}</span>
                <button type="button" className="btn-ghost shrink-0" onClick={salir}>
                  Cerrar sesión
                </button>
              </div>
            ) : (
              <div className="flex gap-3">
                <NavLink to="/entrar" className="btn-primary flex-1">
                  Entrar
                </NavLink>
                <NavLink to="/registro" className="btn-ghost flex-1">
                  Crear cuenta
                </NavLink>
              </div>
            )}
          </div>
        </nav>
      </div>
    </header>
  )
}

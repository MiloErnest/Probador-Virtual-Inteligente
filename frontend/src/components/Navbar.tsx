import { useState } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'

import { useAuth } from '@/auth/AuthContext'
import HealthBadge from '@/components/HealthBadge'
import { NAV_ITEMS } from '@/navigation'

function linkClasses({ isActive }: { isActive: boolean }) {
  const base = 'relative py-1.5 text-sm transition-colors'
  return isActive
    ? `${base} text-ink font-medium`
    : `${base} text-ink-muted hover:text-ink`
}

export default function Navbar() {
  const [open, setOpen] = useState(false)
  const { user, isAuthenticated, logout } = useAuth()
  const navigate = useNavigate()

  // Las secciones que exigen cuenta no se enseñan a quien no ha entrado:
  // llevarian a una redireccion inmediata al formulario de acceso.
  const visibleItems = NAV_ITEMS.filter((item) => !item.requiresAuth || isAuthenticated)

  function handleLogout() {
    logout()
    setOpen(false)
    navigate('/', { replace: true })
  }

  return (
    <header className="sticky top-0 z-20 border-b border-black/[0.07] bg-canvas/85 backdrop-blur">
      <div className="container-page flex h-16 items-center justify-between gap-6">
        <NavLink to="/" className="flex items-center gap-2.5" onClick={() => setOpen(false)}>
          <span className="h-2.5 w-2.5 rounded-full bg-accent" aria-hidden />
          <span className="font-display text-lg leading-none">Atelier</span>
          <span className="hidden text-[11px] uppercase tracking-[0.18em] text-ink-muted sm:inline">
            Virtual
          </span>
        </NavLink>

        <nav className="hidden items-center gap-7 md:flex" aria-label="Principal">
          {visibleItems.map((item) => (
            <NavLink key={item.to} to={item.to} className={linkClasses} end={item.to === '/'}>
              {item.label}
              {!item.ready && (
                <span className="ml-1.5 align-super text-[9px] font-medium tracking-wider text-accent">
                  F{item.phase}
                </span>
              )}
            </NavLink>
          ))}
        </nav>

        <div className="flex items-center gap-3">
          {isAuthenticated ? (
            <div className="hidden items-center gap-3 sm:flex">
              <span className="max-w-[12rem] truncate text-sm text-ink-muted" title={user?.email}>
                {user?.name}
              </span>
              <button type="button" className="btn-ghost px-3.5 py-1.5" onClick={handleLogout}>
                Salir
              </button>
            </div>
          ) : (
            <NavLink to="/entrar" className="btn-primary hidden px-4 py-1.5 sm:inline-flex">
              Entrar
            </NavLink>
          )}

          <HealthBadge />
          <button
            type="button"
            className="btn-ghost px-3 py-1.5 md:hidden"
            aria-expanded={open}
            aria-controls="menu-movil"
            onClick={() => setOpen((value) => !value)}
          >
            {open ? 'Cerrar' : 'Menú'}
          </button>
        </div>
      </div>

      {open && (
        <nav
          id="menu-movil"
          className="container-page grid gap-1 border-t border-black/[0.07] py-3 md:hidden"
          aria-label="Principal (móvil)"
        >
          {visibleItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              onClick={() => setOpen(false)}
              className={({ isActive }) =>
                `rounded-lg px-3 py-2.5 text-sm ${
                  isActive ? 'bg-black/[0.05] font-medium text-ink' : 'text-ink-soft'
                }`
              }
            >
              {item.label}
              {!item.ready && <span className="ml-2 text-[10px] text-accent">Fase {item.phase}</span>}
            </NavLink>
          ))}

          <div className="mt-2 border-t border-black/[0.07] pt-3">
            {isAuthenticated ? (
              <button
                type="button"
                onClick={handleLogout}
                className="w-full rounded-lg px-3 py-2.5 text-left text-sm text-ink-soft"
              >
                Salir ({user?.name})
              </button>
            ) : (
              <NavLink
                to="/entrar"
                onClick={() => setOpen(false)}
                className="block rounded-lg px-3 py-2.5 text-sm font-medium text-ink"
              >
                Entrar
              </NavLink>
            )}
          </div>
        </nav>
      )}
    </header>
  )
}

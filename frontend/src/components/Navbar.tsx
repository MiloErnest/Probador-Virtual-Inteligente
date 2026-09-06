import { useState } from 'react'
import { NavLink } from 'react-router-dom'

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
          {NAV_ITEMS.map((item) => (
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
          {NAV_ITEMS.map((item) => (
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
        </nav>
      )}
    </header>
  )
}

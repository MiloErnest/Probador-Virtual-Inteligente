/** Bloques reutilizables de estado: carga, error, vacío y aviso de fase. */

import type { ReactNode } from 'react'

interface MessageProps {
  title: string
  detail?: string
  action?: ReactNode
}

export function LoadingBlock({ label = 'Cargando…' }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-3 py-16 text-sm text-ink-muted">
      <span className="h-3 w-3 animate-spin rounded-full border-2 border-ink-muted/30 border-t-ink-muted" />
      {label}
    </div>
  )
}

export function ErrorBlock({ title, detail, action }: MessageProps) {
  return (
    <div className="card border-red-200 bg-red-50/60 p-6">
      <h3 className="text-sm font-medium text-red-900">{title}</h3>
      {detail && <p className="mt-1 text-sm text-red-800/80">{detail}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}

export function EmptyBlock({ title, detail, action }: MessageProps) {
  return (
    <div className="card p-10 text-center">
      <h3 className="font-display text-lg">{title}</h3>
      {detail && <p className="mx-auto mt-2 max-w-md text-sm text-ink-muted">{detail}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  )
}

export function PhaseNotice({
  phase,
  title,
  children,
}: {
  phase: number
  title: string
  children: ReactNode
}) {
  return (
    <section className="card overflow-hidden">
      <div className="border-b border-black/[0.07] bg-accent-soft/60 px-6 py-4">
        <span className="pill bg-white text-accent">Fase {phase}</span>
        <h2 className="mt-2 font-display text-xl">{title}</h2>
      </div>
      <div className="space-y-3 px-6 py-6 text-sm leading-relaxed text-ink-soft">{children}</div>
    </section>
  )
}

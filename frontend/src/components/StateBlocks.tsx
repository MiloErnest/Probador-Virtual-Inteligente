/**
 * Bloques reutilizables de estado: carga, error, vacío y aviso.
 *
 * Sin color, un error tiene que distinguirse por otra cosa. Aquí lo hace por
 * peso y por estructura: una barra negra a la izquierda, el rótulo en
 * mayúsculas y el título en negrita. Se ve antes que un recuadro rojo claro,
 * y no obliga a introducir una paleta entera para un caso que, con suerte,
 * casi nunca aparece.
 */

import type { ReactNode } from 'react'

interface MessageProps {
  title: string
  detail?: string
  action?: ReactNode
}

export function LoadingBlock({ label = 'Cargando…' }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-3 py-16 text-sm text-ink-60">
      <span
        className="h-3 w-3 animate-spin rounded-full border border-ink-20 border-t-ink"
        aria-hidden
      />
      {label}
    </div>
  )
}

export function ErrorBlock({ title, detail, action }: MessageProps) {
  return (
    <div role="alert" className="flex gap-4 rounded border border-ink-10 bg-bone p-5 sm:p-6">
      <span className="w-1 shrink-0 rounded-full bg-ink" aria-hidden />
      <div className="min-w-0">
        <p className="rotulo text-ink">Error</p>
        <h3 className="mt-1.5 font-medium">{title}</h3>
        {detail && <p className="mt-1 break-words text-sm leading-relaxed text-ink-60">{detail}</p>}
        {action && <div className="mt-4">{action}</div>}
      </div>
    </div>
  )
}

export function EmptyBlock({ title, detail, action }: MessageProps) {
  return (
    <div className="rounded border border-dashed border-ink-20 px-6 py-16 text-center">
      <h3 className="font-display text-2xl">{title}</h3>
      {detail && (
        <p className="mx-auto mt-2 max-w-md text-sm leading-relaxed text-ink-60">{detail}</p>
      )}
      {action && <div className="mt-6">{action}</div>}
    </div>
  )
}

/**
 * Aviso informativo. Se usa para lo que el probador tiene que dejar claro:
 * qué hace con tu cámara, y hasta dónde llega la vista previa.
 */
export function Notice({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="rounded border border-ink-10 bg-bone p-5">
      <p className="rotulo">{title}</p>
      <div className="mt-2 space-y-2 text-sm leading-relaxed text-ink-80">{children}</div>
    </div>
  )
}

/**
 * Indicador del estado del backend.
 *
 * Es la comprobación visual de que frontend y backend se comunican: si esto
 * está en verde, la Etapa 1 está correctamente cableada.
 */

import { useCallback } from 'react'

import { useApi } from '@/hooks/useApi'
import { fetchHealth } from '@/services/endpoints'

export default function HealthBadge() {
  const fetcher = useCallback((signal: AbortSignal) => fetchHealth(signal), [])
  const { data, loading, error } = useApi(fetcher)

  const { color, label, title } = (() => {
    if (loading) return { color: 'bg-ink-muted', label: 'Conectando', title: 'Consultando /api/health' }
    if (error || !data) return { color: 'bg-red-500', label: 'Sin conexión', title: error ?? 'Backend no disponible' }
    if (data.database === 'down')
      return { color: 'bg-amber-500', label: 'Sin BD', title: 'El backend responde pero PostgreSQL no está disponible' }
    return { color: 'bg-emerald-500', label: 'En línea', title: `${data.service} v${data.version} (${data.environment})` }
  })()

  return (
    <span
      title={title}
      className="hidden items-center gap-2 rounded-full border border-black/10 px-3 py-1.5 text-xs text-ink-soft sm:inline-flex"
    >
      <span className={`h-1.5 w-1.5 rounded-full ${color}`} aria-hidden />
      {label}
    </span>
  )
}

/**
 * Indicador del estado del backend.
 *
 * POR QUE NO ES UN SEMAFORO DE COLORES
 * ------------------------------------
 * Lo habitual sería verde/ámbar/rojo, pero en un sistema sin color de acento
 * esos tres puntos serían lo único coloreado de la pantalla y se convertirían
 * en el centro de atención de una página cuyo tema no es el estado del
 * servidor.
 *
 * El estado se distingue por FORMA —punto lleno, punto hueco, punto que
 * late— y, sobre todo, por la palabra que lo acompaña. Que además es la única
 * forma en que lo entiende alguien que no distingue el rojo del verde.
 */

import { useCallback } from 'react'

import { useApi } from '@/hooks/useApi'
import { fetchHealth } from '@/services/endpoints'

export default function HealthBadge() {
  const fetcher = useCallback((signal: AbortSignal) => fetchHealth(signal), [])
  const { data, loading, error } = useApi(fetcher)

  const estado = (() => {
    if (loading) {
      return {
        punto: 'bg-ink-40 animate-latido',
        label: 'Conectando',
        title: 'Consultando /api/health',
      }
    }
    if (error || !data) {
      return {
        punto: 'border border-ink-40',
        label: 'Sin conexión',
        title: error ?? 'El backend no responde',
      }
    }
    if (data.database === 'down') {
      return {
        punto: 'border border-ink',
        label: 'Sin base',
        title: 'El backend responde, pero PostgreSQL no está disponible',
      }
    }
    return {
      punto: 'bg-ink',
      label: 'En línea',
      title: `${data.service} v${data.version} · ${data.environment}`,
    }
  })()

  return (
    <span
      title={estado.title}
      className="hidden items-center gap-2 rounded-full border border-ink-10 px-3 py-1.5 text-[11px] font-medium text-ink-60 sm:inline-flex"
    >
      <span className={`h-1.5 w-1.5 rounded-full ${estado.punto}`} aria-hidden />
      {estado.label}
    </span>
  )
}

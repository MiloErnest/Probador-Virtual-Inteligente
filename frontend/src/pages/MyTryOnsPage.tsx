/**
 * Historial de pruebas del usuario.
 *
 * Consume el endpoint real /api/try-on-sessions. Hasta que exista
 * autenticación, el identificador de usuario se introduce a mano: es una
 * muleta temporal y deliberadamente visible, no un diseño definitivo.
 */

import { useCallback, useState } from 'react'
import { Link } from 'react-router-dom'

import { EmptyBlock, ErrorBlock, LoadingBlock } from '@/components/StateBlocks'
import { useApi } from '@/hooks/useApi'
import { fetchTryOnSessions } from '@/services/endpoints'

export default function MyTryOnsPage() {
  const [userId, setUserId] = useState(1)

  const fetcher = useCallback(
    (signal: AbortSignal) => fetchTryOnSessions(userId, signal),
    [userId],
  )
  const { data, loading, error, reload } = useApi(fetcher, [userId])

  return (
    <div className="space-y-8">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-3xl">Mis pruebas</h1>
          <p className="mt-1.5 text-sm text-ink-muted">
            Historial de prendas que has probado virtualmente.
          </p>
        </div>

        <label className="flex items-center gap-2 text-xs text-ink-muted">
          <span>ID de usuario (temporal, hasta tener login)</span>
          <input
            type="number"
            min={1}
            value={userId}
            onChange={(event) => setUserId(Math.max(1, Number(event.target.value) || 1))}
            className="w-20 rounded-lg border border-black/10 bg-white px-2.5 py-1.5 text-sm text-ink"
          />
        </label>
      </header>

      {loading && <LoadingBlock label="Cargando historial…" />}

      {error && !loading && (
        <ErrorBlock
          title="No se pudo cargar el historial"
          detail={error}
          action={
            <button type="button" className="btn-ghost" onClick={reload}>
              Reintentar
            </button>
          }
        />
      )}

      {!loading && !error && data && data.length === 0 && (
        <EmptyBlock
          title="Sin pruebas todavía"
          detail="El historial se llenará cuando el probador virtual esté conectado al proveedor de IA."
          action={
            <Link to="/catalogo" className="btn-primary">
              Explorar el catálogo
            </Link>
          }
        />
      )}

      {!loading && !error && data && data.length > 0 && (
        <ul className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {data.map((session) => (
            <li key={session.id} className="card overflow-hidden">
              <div className="aspect-[3/4] bg-canvas">
                {session.output_image_url ? (
                  <img
                    src={session.output_image_url}
                    alt={`Resultado de la prueba ${session.id}`}
                    className="h-full w-full object-cover"
                  />
                ) : (
                  <div className="flex h-full items-center justify-center text-sm text-ink-muted">
                    {session.status === 'failed' ? 'Falló' : 'Procesando…'}
                  </div>
                )}
              </div>
              <div className="flex items-center justify-between p-4 text-xs text-ink-muted">
                <span>Prueba #{session.id}</span>
                <span>{new Date(session.created_at).toLocaleDateString('es')}</span>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

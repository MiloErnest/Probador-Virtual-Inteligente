/**
 * Historial de pruebas del usuario.
 *
 * Etapa 2: desaparece el campo "ID de usuario" que habia que escribir a mano.
 * El backend deduce de quien es el historial a partir del token, asi que la
 * pagina ya no necesita saberlo ni preguntarlo.
 */

import { useCallback } from 'react'
import { Link } from 'react-router-dom'

import { useAuth } from '@/auth/AuthContext'
import { EmptyBlock, ErrorBlock, LoadingBlock } from '@/components/StateBlocks'
import { useApi } from '@/hooks/useApi'
import { fetchTryOnSessions } from '@/services/endpoints'

export default function MyTryOnsPage() {
  const { user } = useAuth()

  const fetcher = useCallback((signal: AbortSignal) => fetchTryOnSessions(signal), [])
  const { data, loading, error, reload } = useApi(fetcher)

  return (
    <div className="space-y-8">
      <header>
        <h1 className="font-display text-3xl">Mis pruebas</h1>
        <p className="mt-1.5 text-sm text-ink-muted">
          Historial de prendas que has probado virtualmente
          {user && <>, de la cuenta {user.email}</>}.
        </p>
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
          title="Sin pruebas todavia"
          detail="El historial se llenara cuando el probador virtual este conectado al proveedor de IA."
          action={
            <Link to="/catalogo" className="btn-primary">
              Explorar el catalogo
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
                    {session.status === 'failed' ? 'Fallo' : 'Procesando…'}
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

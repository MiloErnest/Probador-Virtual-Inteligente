/**
 * Perfil del usuario autenticado.
 *
 * Enseña la cuenta y el estado del sistema. Lo segundo no es relleno: cuando
 * el probador no carga las prendas, lo primero que hay que saber es si el
 * backend responde y si la base de datos está levantada.
 */

import { useCallback } from 'react'
import { useNavigate } from 'react-router-dom'

import { useAuth } from '@/auth/AuthContext'
import { ErrorBlock, LoadingBlock } from '@/components/StateBlocks'
import { useApi } from '@/hooks/useApi'
import { fetchHealth } from '@/services/endpoints'

export default function ProfilePage() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  const fetcher = useCallback((signal: AbortSignal) => fetchHealth(signal), [])
  const { data, loading, error } = useApi(fetcher)

  function salir() {
    logout()
    navigate('/', { replace: true })
  }

  return (
    <div className="wrap max-w-3xl space-y-12">
      <header className="border-b border-ink-10 pb-6">
        <p className="rotulo">Perfil</p>
        <h1 className="mt-3 font-display text-titulo">{user?.name}</h1>
        <p className="mt-2 text-sm text-ink-60">{user?.email}</p>
      </header>

      <section>
        <h2 className="rotulo">Tu cuenta</h2>

        {user && (
          <Lista
            filas={[
              ['Nombre', user.name],
              ['Correo electrónico', user.email],
              ['Cuenta creada', new Date(user.created_at).toLocaleDateString('es')],
            ]}
          />
        )}

        <div className="mt-6">
          <button type="button" className="btn-ghost" onClick={salir}>
            Cerrar sesión
          </button>
          <p className="mt-3 max-w-lg text-xs leading-relaxed text-ink-60">
            Cerrar sesión descarta el token en este navegador. No hay lista de revocación en el
            servidor, así que el token seguiría siendo válido hasta caducar.
          </p>
        </div>
      </section>

      <section>
        <h2 className="rotulo">Estado del sistema</h2>

        {loading && <LoadingBlock label="Consultando el backend…" />}

        {error && !loading && (
          <div className="mt-4">
            <ErrorBlock
              title="Backend no disponible"
              detail={`${error} Comprueba que uvicorn esté ejecutándose.`}
            />
          </div>
        )}

        {data && !loading && !error && (
          <Lista
            filas={[
              ['Servicio', data.service],
              ['Versión', data.version],
              ['Entorno', data.environment],
              ['Base de datos', data.database === 'up' ? 'Conectada' : 'No disponible'],
            ]}
          />
        )}
      </section>
    </div>
  )
}

function Lista({ filas }: { filas: [string, string][] }) {
  return (
    <dl className="mt-4 divide-y divide-ink-10 border-y border-ink-10 text-sm">
      {filas.map(([etiqueta, valor]) => (
        <div key={etiqueta} className="flex items-center justify-between gap-4 py-3.5">
          <dt className="text-ink-60">{etiqueta}</dt>
          <dd className="truncate font-medium">{valor}</dd>
        </div>
      ))}
    </dl>
  )
}

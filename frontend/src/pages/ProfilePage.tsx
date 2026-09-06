/**
 * Perfil del usuario autenticado.
 *
 * Etapa 2: el aviso de "cuenta pendiente de autenticacion" desaparece; la
 * pagina muestra la cuenta real. Solo es accesible con sesion iniciada
 * (ver RequireAuth en App.tsx).
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

  function handleLogout() {
    logout()
    navigate('/', { replace: true })
  }

  return (
    <div className="max-w-3xl space-y-8">
      <header>
        <h1 className="font-display text-3xl">Perfil</h1>
        <p className="mt-1.5 text-sm text-ink-muted">Tu cuenta y el estado del sistema.</p>
      </header>

      <section>
        <h2 className="font-display text-xl">Tu cuenta</h2>

        {user && (
          <dl className="card mt-4 divide-y divide-black/[0.07] text-sm">
            {[
              ['Nombre', user.name],
              ['Correo electronico', user.email],
              ['Cuenta creada', new Date(user.created_at).toLocaleDateString('es')],
            ].map(([label, value]) => (
              <div key={label} className="flex items-center justify-between px-5 py-3.5">
                <dt className="text-ink-muted">{label}</dt>
                <dd className="font-medium">{value}</dd>
              </div>
            ))}
          </dl>
        )}

        <div className="mt-4">
          <button type="button" className="btn-ghost" onClick={handleLogout}>
            Cerrar sesion
          </button>
          <p className="mt-2 text-xs text-ink-muted">
            Cerrar sesion descarta el token en este navegador. No hay lista de revocacion
            en el servidor, asi que el token seguiria siendo valido hasta caducar.
          </p>
        </div>
      </section>

      <section>
        <h2 className="font-display text-xl">Estado del sistema</h2>

        {loading && <LoadingBlock label="Consultando el backend…" />}

        {error && !loading && (
          <div className="mt-4">
            <ErrorBlock
              title="Backend no disponible"
              detail={`${error} Comprueba que uvicorn este ejecutandose.`}
            />
          </div>
        )}

        {data && !loading && !error && (
          <dl className="card mt-4 divide-y divide-black/[0.07] text-sm">
            {[
              ['Servicio', data.service],
              ['Version', data.version],
              ['Entorno', data.environment],
              ['Base de datos', data.database === 'up' ? 'Conectada' : 'No disponible'],
            ].map(([label, value]) => (
              <div key={label} className="flex items-center justify-between px-5 py-3.5">
                <dt className="text-ink-muted">{label}</dt>
                <dd className="font-medium">{value}</dd>
              </div>
            ))}
          </dl>
        )}
      </section>
    </div>
  )
}

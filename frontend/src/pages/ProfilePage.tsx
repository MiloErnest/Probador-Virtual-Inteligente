import { useCallback } from 'react'

import { ErrorBlock, LoadingBlock, PhaseNotice } from '@/components/StateBlocks'
import { useApi } from '@/hooks/useApi'
import { fetchHealth } from '@/services/endpoints'

export default function ProfilePage() {
  const fetcher = useCallback((signal: AbortSignal) => fetchHealth(signal), [])
  const { data, loading, error } = useApi(fetcher)

  return (
    <div className="max-w-3xl space-y-8">
      <header>
        <h1 className="font-display text-3xl">Perfil</h1>
        <p className="mt-1.5 text-sm text-ink-muted">
          Tu cuenta y el estado del sistema.
        </p>
      </header>

      <PhaseNotice phase={1} title="Cuenta pendiente de autenticación">
        <p>
          El backend ya registra usuarios con la contraseña cifrada
          (<code className="rounded bg-black/[0.05] px-1.5 py-0.5 text-xs">POST /api/users</code>),
          pero todavía no existe inicio de sesión. Añadir JWT es la primera tarea de la Etapa 2.
        </p>
      </PhaseNotice>

      <section>
        <h2 className="font-display text-xl">Estado del sistema</h2>

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
          <dl className="card mt-4 divide-y divide-black/[0.07] text-sm">
            {[
              ['Servicio', data.service],
              ['Versión', data.version],
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

/**
 * Catálogo de prendas.
 *
 * Los datos salen de PostgreSQL, pasan por FastAPI y se pintan aquí. Cada
 * tarjeta enlaza al probador con la prenda ya elegida: el catálogo no es una
 * galería que mirar, es por donde se entra a probarse algo.
 */

import { useCallback, useState } from 'react'
import { Link } from 'react-router-dom'

import { useAuth } from '@/auth/AuthContext'
import GarmentCard from '@/components/GarmentCard'
import { EmptyBlock, ErrorBlock, LoadingBlock } from '@/components/StateBlocks'
import { useApi } from '@/hooks/useApi'
import { fetchGarments } from '@/services/endpoints'
import { CATEGORY_LABELS, type GarmentCategory } from '@/types'

const CATEGORIES = Object.keys(CATEGORY_LABELS) as GarmentCategory[]

export default function CatalogPage() {
  const [category, setCategory] = useState<GarmentCategory | undefined>(undefined)
  const { isAuthenticated } = useAuth()

  const fetcher = useCallback(
    (signal: AbortSignal) => fetchGarments({ category, signal }),
    [category],
  )
  const { data, loading, error, reload } = useApi(fetcher, [category])

  return (
    <div className="wrap space-y-10">
      <header>
        <p className="rotulo">Catálogo</p>
        <div className="mt-4 flex flex-wrap items-end justify-between gap-x-8 gap-y-4 border-b border-ink-10 pb-6">
          <h1 className="font-display text-titulo">Prendas disponibles</h1>
          {data && (
            <p className="text-sm text-ink-60">
              {data.length} {data.length === 1 ? 'prenda' : 'prendas'}
              {!isAuthenticated && ' · entra para probártelas'}
            </p>
          )}
        </div>
      </header>

      {/* El filtro se desplaza de lado en móvil en vez de envolverse en tres
          líneas: así la rejilla de prendas empieza siempre a la misma altura. */}
      <div
        className="-mx-5 flex gap-2 overflow-x-auto px-5 sm:mx-0 sm:flex-wrap sm:px-0 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
        role="group"
        aria-label="Filtrar por categoría"
      >
        <BotonFiltro activo={category === undefined} onClick={() => setCategory(undefined)}>
          Todas
        </BotonFiltro>
        {CATEGORIES.map((value) => (
          <BotonFiltro
            key={value}
            activo={category === value}
            onClick={() => setCategory(value)}
          >
            {CATEGORY_LABELS[value]}
          </BotonFiltro>
        ))}
      </div>

      {loading && <LoadingBlock label="Cargando catálogo…" />}

      {error && !loading && (
        <ErrorBlock
          title="No se pudo cargar el catálogo"
          detail={error}
          action={
            <button type="button" className="btn-ghost" onClick={reload}>
              Reintentar
            </button>
          }
        />
      )}

      {!loading && !error && data?.length === 0 && (
        <EmptyBlock
          title="Todavía no hay prendas"
          detail="Ejecuta `python -m scripts.seed --con-prendas-reales` en la carpeta backend para cargar el catálogo de ejemplo."
        />
      )}

      {!loading && !error && data && data.length > 0 && (
        <div className="grid grid-cols-2 gap-x-4 gap-y-8 sm:grid-cols-3 sm:gap-x-5 lg:grid-cols-4">
          {data.map((garment) => (
            <GarmentCard key={garment.id} garment={garment} probable={isAuthenticated} />
          ))}
        </div>
      )}

      {!isAuthenticated && data && data.length > 0 && (
        <div className="flex flex-col items-start gap-4 border-t border-ink-10 pt-8 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-sm text-ink-60">
            Para probártelas delante de la cámara hace falta una cuenta.
          </p>
          <Link to="/entrar" className="btn-primary shrink-0">
            Entrar
          </Link>
        </div>
      )}
    </div>
  )
}

function BotonFiltro({
  activo,
  onClick,
  children,
}: {
  activo: boolean
  onClick: () => void
  children: React.ReactNode
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={activo}
      className={`shrink-0 whitespace-nowrap rounded-full border px-4 py-1.5 text-sm transition ${
        activo
          ? 'border-ink bg-ink text-paper'
          : 'border-ink-20 text-ink-60 hover:border-ink hover:text-ink'
      }`}
    >
      {children}
    </button>
  )
}

/**
 * Catálogo de prendas.
 *
 * Esta pantalla es la prueba de extremo a extremo de la Etapa 1: los datos
 * salen de PostgreSQL, pasan por FastAPI y se pintan aquí.
 */

import { useCallback, useState } from 'react'

import GarmentCard from '@/components/GarmentCard'
import { EmptyBlock, ErrorBlock, LoadingBlock } from '@/components/StateBlocks'
import { useApi } from '@/hooks/useApi'
import { fetchGarments } from '@/services/endpoints'
import { CATEGORY_LABELS, type GarmentCategory } from '@/types'

const CATEGORIES = Object.keys(CATEGORY_LABELS) as GarmentCategory[]

export default function CatalogPage() {
  const [category, setCategory] = useState<GarmentCategory | undefined>(undefined)

  const fetcher = useCallback(
    (signal: AbortSignal) => fetchGarments({ category, signal }),
    [category],
  )
  const { data, loading, error, reload } = useApi(fetcher, [category])

  return (
    <div className="space-y-8">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-3xl">Catálogo</h1>
          <p className="mt-1.5 text-sm text-ink-muted">
            Prendas disponibles para probar virtualmente.
          </p>
        </div>

        <div className="flex flex-wrap gap-2" role="group" aria-label="Filtrar por categoría">
          <button
            type="button"
            onClick={() => setCategory(undefined)}
            className={`pill border px-3 py-1.5 ${
              category === undefined
                ? 'border-ink bg-ink text-white'
                : 'border-black/10 text-ink-soft hover:bg-black/[0.04]'
            }`}
          >
            Todas
          </button>
          {CATEGORIES.map((value) => (
            <button
              key={value}
              type="button"
              onClick={() => setCategory(value)}
              className={`pill border px-3 py-1.5 ${
                category === value
                  ? 'border-ink bg-ink text-white'
                  : 'border-black/10 text-ink-soft hover:bg-black/[0.04]'
              }`}
            >
              {CATEGORY_LABELS[value]}
            </button>
          ))}
        </div>
      </header>

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

      {!loading && !error && data && data.length === 0 && (
        <EmptyBlock
          title="Todavía no hay prendas"
          detail="Ejecuta `python -m scripts.seed` en la carpeta backend para cargar el catálogo de ejemplo."
        />
      )}

      {!loading && !error && data && data.length > 0 && (
        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
          {data.map((garment) => (
            <GarmentCard key={garment.id} garment={garment} />
          ))}
        </div>
      )}
    </div>
  )
}

/**
 * Catálogo de telas: el escaparate de la tienda textil.
 *
 * POR QUÉ CADA FICHA ENSEÑA TANTO DATO
 * ------------------------------------
 * Porque la métrica del producto es la conversión prueba→compra, y nadie
 * compra tela sin saber el ancho del rollo. Una galería de cuadraditos de
 * colores es bonita y no sirve: la modista necesita el ancho para saber si le
 * salen las piezas del patrón, el gramaje para saber si eso cae o se sostiene,
 * y la referencia para poder pedirla.
 */

import { useCallback, useState } from 'react'
import { Link } from 'react-router-dom'

import { useAuth } from '@/auth/AuthContext'
import { EmptyBlock, ErrorBlock, LoadingBlock } from '@/components/StateBlocks'
import { useApi } from '@/hooks/useApi'
import { fetchFabrics } from '@/services/endpoints'
import { FABRIC_PATTERN_LABELS, type Fabric, type FabricPattern } from '@/types'

const PATTERNS = Object.keys(FABRIC_PATTERN_LABELS) as FabricPattern[]

export default function FabricsPage() {
  const [pattern, setPattern] = useState<FabricPattern | undefined>(undefined)
  const { isAuthenticated } = useAuth()

  const fetcher = useCallback(
    (signal: AbortSignal) => fetchFabrics({ pattern, signal }),
    [pattern],
  )
  const { data, loading, error, reload } = useApi(fetcher, [pattern])

  return (
    <div className="wrap space-y-10">
      <header>
        <p className="rotulo">Catálogo</p>
        <div className="mt-4 flex flex-wrap items-end justify-between gap-x-8 gap-y-4 border-b border-ink-10 pb-6">
          <div>
            <h1 className="font-display text-titulo">Telas</h1>
            <p className="mt-2 max-w-xl text-sm leading-relaxed text-ink-60">
              Elige una tela y pruébala sobre tu propia prenda antes de comprar el metraje.
            </p>
          </div>
          {data && (
            <p className="text-sm text-ink-60">
              {data.length} {data.length === 1 ? 'tela' : 'telas'}
            </p>
          )}
        </div>
      </header>

      <div
        className="-mx-5 flex gap-2 overflow-x-auto px-5 sm:mx-0 sm:flex-wrap sm:px-0 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
        role="group"
        aria-label="Filtrar por dibujo"
      >
        <Filtro activo={pattern === undefined} onClick={() => setPattern(undefined)}>
          Todas
        </Filtro>
        {PATTERNS.map((value) => (
          <Filtro key={value} activo={pattern === value} onClick={() => setPattern(value)}>
            {FABRIC_PATTERN_LABELS[value]}
          </Filtro>
        ))}
      </div>

      {loading && <LoadingBlock label="Cargando el catálogo…" />}

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
          title="Todavía no hay telas"
          detail="Ejecuta `python -m scripts.seed_telas` en la carpeta backend para cargar el catálogo de ejemplo."
        />
      )}

      {!loading && !error && data && data.length > 0 && (
        <div className="grid grid-cols-2 gap-x-4 gap-y-8 sm:grid-cols-3 sm:gap-x-5 lg:grid-cols-4">
          {data.map((tela) => (
            <FichaDeTela key={tela.id} tela={tela} />
          ))}
        </div>
      )}

      <div className="flex flex-col items-start gap-4 border-t border-ink-10 pt-8 sm:flex-row sm:items-center sm:justify-between">
        <p className="max-w-lg text-sm text-ink-60">
          Para ver una tela sobre tu diseño, sube una fotografía de la prenda o un boceto
          en tu taller.
        </p>
        <Link to={isAuthenticated ? '/taller' : '/entrar'} className="btn-primary shrink-0">
          {isAuthenticated ? 'Ir a mi taller' : 'Entrar'}
        </Link>
      </div>
    </div>
  )
}

function FichaDeTela({ tela }: { tela: Fabric }) {
  return (
    <article className="group">
      <div
        className="relative aspect-square overflow-hidden rounded border border-ink-10"
        // El color dominante se pinta detrás de la imagen: mientras carga, la
        // ficha ya dice de qué color es la tela en vez de enseñar un hueco.
        style={{ backgroundColor: tela.color_hex ?? '#f7f7f5' }}
      >
        {tela.photo_url && (
          <img
            src={tela.photo_url}
            alt={tela.name}
            loading="lazy"
            className="h-full w-full object-cover transition-transform duration-700 ease-out group-hover:scale-[1.06]"
          />
        )}
        {tela.texture_url === null && (
          <span className="absolute left-2 top-2 rounded-full bg-ink/80 px-2 py-1 text-[10px] text-paper backdrop-blur">
            Sin mosaico
          </span>
        )}
      </div>

      <div className="px-1 pt-3">
        <h3 className="text-sm font-medium leading-snug">{tela.name}</h3>
        {tela.reference && (
          <p className="mt-0.5 font-mono text-[11px] text-ink-40">{tela.reference}</p>
        )}

        <dl className="mt-2 space-y-0.5 text-xs text-ink-60">
          {tela.composition && <dd>{tela.composition}</dd>}
          <dd className="flex flex-wrap gap-x-3">
            {tela.width_cm && <span>{tela.width_cm} cm de ancho</span>}
            {tela.weight_gsm && <span>{tela.weight_gsm} g/m²</span>}
          </dd>
        </dl>

        {tela.price_per_meter !== null && (
          <p className="mt-2 text-sm font-medium">
            {tela.price_per_meter.toFixed(2)} {tela.currency}
            <span className="text-xs font-normal text-ink-60"> / metro</span>
          </p>
        )}
      </div>
    </article>
  )
}

function Filtro({
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

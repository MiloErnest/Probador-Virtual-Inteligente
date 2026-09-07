/**
 * Disenar con IA (Fase 2).
 *
 * Flujo: describir -> generar -> ver -> iterar -> probarselo.
 *
 * Mismo contrato asincrono que el probador: el backend responde 202 con el
 * diseno en `pending` y esta pantalla sondea hasta `completed` o `failed`.
 * Se repite el patron a proposito; quien entienda una pantalla entiende la
 * otra.
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { EmptyBlock, ErrorBlock, LoadingBlock } from '@/components/StateBlocks'
import { useApi } from '@/hooks/useApi'
import { createDesign, fetchDesign, fetchDesigns, refineDesign } from '@/services/endpoints'
import type { Design } from '@/types'

const POLL_INTERVAL_MS = 1500
const POLL_TIMEOUT_MS = 90_000

/** Ejemplos que rellenan el campo de un clic. Bajan mucho la friccion de
 *  empezar: mirar un cuadro de texto vacio paraliza. */
const EJEMPLOS = [
  'vestido largo rojo de gala con escote en V',
  'abrigo de lana verde hasta la rodilla',
  'pantalon vaquero azul de pierna ancha',
  'camisa blanca de lino oversize',
]

export default function DesignAIPage() {
  const navigate = useNavigate()

  const fetcher = useCallback((signal: AbortSignal) => fetchDesigns(signal), [])
  const { data: historial, loading, error: historialError, reload } = useApi(fetcher)

  const [prompt, setPrompt] = useState('')
  const [refinement, setRefinement] = useState('')
  const [actual, setActual] = useState<Design | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [enviando, setEnviando] = useState(false)

  const generando = actual?.status === 'pending' || actual?.status === 'processing'
  const iniciado = useRef(0)

  useEffect(() => {
    if (actual === null || !generando) return

    if (iniciado.current === 0) iniciado.current = Date.now()
    const controller = new AbortController()
    let activo = true

    const timer = window.setInterval(async () => {
      if (Date.now() - iniciado.current > POLL_TIMEOUT_MS) {
        window.clearInterval(timer)
        if (activo) setError('El diseno esta tardando demasiado. Vuelve a intentarlo.')
        return
      }
      try {
        const nuevo = await fetchDesign(actual.id, controller.signal)
        if (!activo) return
        setActual(nuevo)
        // Al terminar se refresca el historial para que la version nueva
        // aparezca en la lista sin recargar la pagina.
        if (nuevo.status === 'completed' || nuevo.status === 'failed') reload()
      } catch {
        // Un corte puntual de red no debe abortar el sondeo.
      }
    }, POLL_INTERVAL_MS)

    return () => {
      activo = false
      controller.abort()
      window.clearInterval(timer)
    }
  }, [actual, generando, reload])

  async function generar(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    setEnviando(true)
    iniciado.current = 0
    try {
      setActual(await createDesign(prompt))
    } catch (causa) {
      setError(causa instanceof Error ? causa.message : 'No se pudo generar el diseno.')
    } finally {
      setEnviando(false)
    }
  }

  async function iterar(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (actual === null) return
    setError(null)
    setEnviando(true)
    iniciado.current = 0
    try {
      const hijo = await refineDesign(actual.id, refinement)
      setActual(hijo)
      setRefinement('')
    } catch (causa) {
      setError(causa instanceof Error ? causa.message : 'No se pudo iterar el diseno.')
    } finally {
      setEnviando(false)
    }
  }

  return (
    <div className="max-w-5xl space-y-8">
      <header>
        <h1 className="font-display text-3xl">Disenar con IA</h1>
        <p className="mt-1.5 text-sm text-ink-muted">
          Describe una prenda con tus palabras y generala. Luego puedes irla afinando.
        </p>
      </header>

      <div className="card border-amber-200 bg-amber-50/60 px-5 py-4 text-sm text-amber-900">
        <strong className="font-medium">Generador simulado, todavia no es IA.</strong> Dibuja
        siluetas a partir de palabras que reconoce (prenda y color). El modelo real se
        conectara despues y esta pantalla no cambiara.
      </div>

      {error && <ErrorBlock title="Algo ha fallado" detail={error} />}

      <section className="space-y-3">
        <h2 className="font-display text-xl">1. Describe la prenda</h2>
        <form onSubmit={generar} className="space-y-3">
          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            rows={3}
            maxLength={1000}
            placeholder="Ej: vestido largo rojo de gala con escote en V"
            className="w-full rounded-lg border border-black/10 bg-white px-3.5 py-2.5 text-sm"
          />
          <div className="flex flex-wrap gap-2">
            {EJEMPLOS.map((ejemplo) => (
              <button
                key={ejemplo}
                type="button"
                onClick={() => setPrompt(ejemplo)}
                className="rounded-full border border-black/10 px-3 py-1 text-xs text-ink-muted hover:bg-black/[0.04]"
              >
                {ejemplo}
              </button>
            ))}
          </div>
          <button
            type="submit"
            className="btn-primary"
            disabled={enviando || generando || prompt.trim().length < 3}
          >
            {enviando ? 'Enviando…' : 'Generar diseno'}
          </button>
        </form>
      </section>

      {actual !== null && (
        <section className="space-y-4">
          <h2 className="font-display text-xl">2. Resultado</h2>

          {generando && <LoadingBlock label="Generando el diseno…" />}

          {actual.status === 'failed' && (
            <ErrorBlock
              title="No se pudo generar"
              detail={actual.error_message ?? 'Error desconocido.'}
            />
          )}

          {actual.status === 'completed' && actual.image_url && (
            <div className="grid gap-6 sm:grid-cols-[minmax(0,320px)_1fr]">
              <figure className="card overflow-hidden">
                <img
                  src={actual.image_url}
                  alt={actual.prompt}
                  className="w-full bg-canvas object-contain"
                />
                <figcaption className="px-4 py-3 text-xs text-ink-muted">
                  {actual.parent_id !== null && <span className="pill bg-accent-soft text-accent">Iteracion</span>}
                  <span className="mt-1 block">{actual.prompt}</span>
                  {actual.refinement && (
                    <span className="mt-1 block italic">Cambio: {actual.refinement}</span>
                  )}
                </figcaption>
              </figure>

              <div className="space-y-5">
                <form onSubmit={iterar} className="space-y-2">
                  <label htmlFor="refinamiento" className="block text-sm font-medium">
                    Afinar el diseno
                  </label>
                  <p className="text-xs text-ink-muted">
                    Escribe solo lo que quieres cambiar. Se crea una version nueva; esta se
                    conserva.
                  </p>
                  <input
                    id="refinamiento"
                    value={refinement}
                    onChange={(e) => setRefinement(e.target.value)}
                    maxLength={1000}
                    placeholder="Ej: que sea azul y mas corto"
                    className="w-full rounded-lg border border-black/10 bg-white px-3.5 py-2.5 text-sm"
                  />
                  <button
                    type="submit"
                    className="btn-ghost"
                    disabled={enviando || generando || refinement.trim().length < 3}
                  >
                    Crear version nueva
                  </button>
                </form>

                <div className="border-t border-black/[0.07] pt-5">
                  <p className="mb-2 text-sm">Cuando te guste, pruebatelo:</p>
                  <button
                    type="button"
                    className="btn-primary"
                    onClick={() => navigate('/probador', { state: { designId: actual.id } })}
                  >
                    Probarme este diseno
                  </button>
                </div>
              </div>
            </div>
          )}
        </section>
      )}

      <section className="space-y-3">
        <h2 className="font-display text-xl">Tus disenos</h2>

        {loading && <LoadingBlock label="Cargando tus disenos…" />}
        {historialError && !loading && (
          <ErrorBlock title="No se pudo cargar el historial" detail={historialError} />
        )}

        {!loading && !historialError && historial && historial.length === 0 && (
          <EmptyBlock
            title="Todavia no has generado nada"
            detail="Describe una prenda arriba y pulsa Generar."
          />
        )}

        {historial && historial.length > 0 && (
          <ul className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
            {historial.map((diseno) => (
              <li key={diseno.id}>
                <button
                  type="button"
                  onClick={() => {
                    setActual(diseno)
                    setError(null)
                  }}
                  className="card w-full overflow-hidden text-left hover:border-black/20"
                >
                  <div className="aspect-[4/5] bg-canvas">
                    {diseno.image_url ? (
                      <img
                        src={diseno.image_url}
                        alt={diseno.prompt}
                        className="h-full w-full object-contain"
                      />
                    ) : (
                      <div className="flex h-full items-center justify-center text-xs text-ink-muted">
                        {diseno.status === 'failed' ? 'Fallo' : 'Generando…'}
                      </div>
                    )}
                  </div>
                  <span className="block truncate p-2.5 text-[11px] text-ink-muted">
                    {diseno.parent_id !== null && '↳ '}
                    {diseno.refinement ?? diseno.prompt}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}

/**
 * Probador virtual.
 *
 * Flujo: elegir prenda -> subir foto -> enviar -> sondear -> ver resultado.
 *
 * POR QUE SE SONDEA
 * -----------------
 * El backend responde 202 con la prueba en estado `pending`; el resultado no
 * viene en esa respuesta, porque generarlo tarda. Asi que esta pantalla
 * consulta el estado cada pocos segundos hasta que sea `completed` o `failed`.
 *
 * Es la solucion mas simple que funciona. Con WebSockets el resultado llegaria
 * empujado en vez de preguntando, pero eso es una pieza de infraestructura mas
 * para un problema que hoy no existe: hay un usuario y una prueba cada vez.
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'

import { EmptyBlock, ErrorBlock, LoadingBlock } from '@/components/StateBlocks'
import { useApi } from '@/hooks/useApi'
import {
  createTryOnSession,
  fetchDesigns,
  fetchGarments,
  fetchTryOnSession,
} from '@/services/endpoints'
import type { Design, Garment, TryOnSession } from '@/types'

/** Cada cuanto se pregunta por el estado, en milisegundos. */
const POLL_INTERVAL_MS = 2000

/** Corte de seguridad: si a los 2 minutos no ha terminado, se deja de sondear. */
const POLL_TIMEOUT_MS = 120_000

const MAX_PHOTO_MB = 8

/** De donde sale la prenda que se prueba. El backend exige exactamente una. */
type Origen = { tipo: 'catalogo'; id: number } | { tipo: 'diseno'; id: number }

export default function TryOnPage() {
  const location = useLocation()

  const fetcher = useCallback((signal: AbortSignal) => fetchGarments({ signal }), [])
  const { data: garments, loading: loadingGarments, error: garmentsError } = useApi(fetcher)

  const disenosFetcher = useCallback((signal: AbortSignal) => fetchDesigns(signal), [])
  const { data: disenos } = useApi(disenosFetcher)

  // 'Probarme este diseno' desde la pantalla de disenos llega por aqui.
  const disenoInicial = (location.state as { designId?: number } | null)?.designId
  const [origen, setOrigen] = useState<Origen | null>(
    disenoInicial !== undefined ? { tipo: 'diseno', id: disenoInicial } : null,
  )
  const [photo, setPhoto] = useState<File | null>(null)
  const [photoPreview, setPhotoPreview] = useState<string | null>(null)
  const [session, setSession] = useState<TryOnSession | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  // Solo se pueden probar prendas que tengan imagen: el proveedor necesita
  // las dos fotos. Las demas se ocultan en vez de fallar al enviar.
  const wearable = (garments ?? []).filter((g: Garment) => g.image_url !== null)
  // Y solo los disenos ya generados.
  const disenosListos = (disenos ?? []).filter(
    (d: Design) => d.status === 'completed' && d.image_url !== null,
  )

  // La URL del objeto File hay que revocarla a mano; si no, el navegador
  // retiene la imagen en memoria hasta recargar la pagina.
  useEffect(() => {
    if (photo === null) {
      setPhotoPreview(null)
      return
    }
    const url = URL.createObjectURL(photo)
    setPhotoPreview(url)
    return () => URL.revokeObjectURL(url)
  }, [photo])

  const isRunning = session?.status === 'pending' || session?.status === 'processing'

  // Sondeo. Se apoya en un ref para el temporizador para poder cancelarlo
  // tanto al terminar como al desmontar la pantalla.
  const startedAt = useRef<number>(0)
  useEffect(() => {
    if (session === null || !isRunning) return

    if (startedAt.current === 0) startedAt.current = Date.now()
    const controller = new AbortController()
    let active = true

    const timer = window.setInterval(async () => {
      if (Date.now() - startedAt.current > POLL_TIMEOUT_MS) {
        window.clearInterval(timer)
        if (active) setError('La prueba esta tardando demasiado. Vuelve a intentarlo.')
        return
      }
      try {
        const actual = await fetchTryOnSession(session.id, controller.signal)
        if (active) setSession(actual)
      } catch {
        // Un fallo puntual de red no debe cortar el sondeo: puede ser un
        // corte de un segundo. Si es permanente, salta el corte por tiempo.
      }
    }, POLL_INTERVAL_MS)

    return () => {
      active = false
      controller.abort()
      window.clearInterval(timer)
    }
  }, [session, isRunning])

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (origen === null || photo === null) return

    setError(null)
    setSubmitting(true)
    startedAt.current = 0
    try {
      setSession(
        await createTryOnSession(
          origen.tipo === 'catalogo' ? { garmentId: origen.id } : { designId: origen.id },
          photo,
        ),
      )
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'No se pudo crear la prueba.')
    } finally {
      setSubmitting(false)
    }
  }

  function reset() {
    setSession(null)
    setError(null)
    startedAt.current = 0
  }

  return (
    <div className="max-w-4xl space-y-8">
      <header>
        <h1 className="font-display text-3xl">Probador virtual</h1>
        <p className="mt-1.5 text-sm text-ink-muted">
          Sube una foto tuya, elige una prenda y genera el resultado.
        </p>
      </header>

      <div className="card border-amber-200 bg-amber-50/60 px-5 py-4 text-sm text-amber-900">
        <strong className="font-medium">Vista previa, todavia no es IA.</strong> Ahora mismo
        la prenda se superpone sobre la foto para que el circuito completo funcione. El
        modelo de prueba virtual real se conectara en el siguiente paso, y esta misma
        pantalla no cambiara.
      </div>

      {error && <ErrorBlock title="Algo ha fallado" detail={error} />}

      {session === null && (
        <form onSubmit={handleSubmit} className="space-y-8">
          <section className="space-y-3">
            <h2 className="font-display text-xl">1. Elige una prenda</h2>

            {disenosListos.length > 0 && (
              <div className="space-y-2">
                <h3 className="text-sm font-medium">Tus disenos</h3>
                <ul className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
                  {disenosListos.map((diseno) => {
                    const elegido = origen?.tipo === 'diseno' && origen.id === diseno.id
                    return (
                      <li key={diseno.id}>
                        <button
                          type="button"
                          onClick={() => setOrigen({ tipo: 'diseno', id: diseno.id })}
                          aria-pressed={elegido}
                          className={`card w-full overflow-hidden text-left transition ${
                            elegido ? 'ring-2 ring-accent' : 'hover:border-black/20'
                          }`}
                        >
                          <div className="aspect-[3/4] bg-canvas">
                            <img
                              src={diseno.image_url ?? ''}
                              alt={diseno.prompt}
                              className="h-full w-full object-contain"
                            />
                          </div>
                          <span className="block truncate p-3 text-xs">{diseno.prompt}</span>
                        </button>
                      </li>
                    )
                  })}
                </ul>
                <h3 className="pt-2 text-sm font-medium">Del catalogo</h3>
              </div>
            )}

            {loadingGarments && <LoadingBlock label="Cargando el catalogo…" />}

            {garmentsError && !loadingGarments && (
              <ErrorBlock title="No se pudo cargar el catalogo" detail={garmentsError} />
            )}

            {!loadingGarments && !garmentsError && wearable.length === 0 && (
              <EmptyBlock
                title="Ninguna prenda tiene imagen todavia"
                detail="Para probar una prenda hace falta su fotografia. Subelas desde el catalogo, genera un diseno propio, o usa el script de datos de ejemplo."
                action={
                  <Link to="/catalogo" className="btn-primary">
                    Ver el catalogo
                  </Link>
                }
              />
            )}

            {wearable.length > 0 && (
              <ul className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
                {wearable.map((garment) => {
                  const selected = origen?.tipo === 'catalogo' && origen.id === garment.id
                  return (
                    <li key={garment.id}>
                      <button
                        type="button"
                        onClick={() => setOrigen({ tipo: 'catalogo', id: garment.id })}
                        aria-pressed={selected}
                        className={`card w-full overflow-hidden text-left transition ${
                          selected ? 'ring-2 ring-accent' : 'hover:border-black/20'
                        }`}
                      >
                        <div className="aspect-[3/4] bg-canvas">
                          <img
                            src={garment.image_url ?? ''}
                            alt={garment.name}
                            className="h-full w-full object-cover"
                          />
                        </div>
                        <span className="block truncate p-3 text-xs">{garment.name}</span>
                      </button>
                    </li>
                  )
                })}
              </ul>
            )}
          </section>

          <section className="space-y-3">
            <h2 className="font-display text-xl">2. Sube tu foto</h2>
            <p className="text-sm text-ink-muted">
              JPEG, PNG o WebP, hasta {MAX_PHOTO_MB} MB. Funciona mejor con una foto de
              cuerpo entero o medio cuerpo, de frente y con fondo despejado.
            </p>

            <div className="flex flex-wrap items-start gap-5">
              <input
                type="file"
                accept="image/jpeg,image/png,image/webp"
                onChange={(event) => setPhoto(event.target.files?.[0] ?? null)}
                className="text-sm file:mr-3 file:rounded-full file:border-0 file:bg-ink file:px-4 file:py-2 file:text-sm file:text-white"
              />
              {photoPreview && (
                <img
                  src={photoPreview}
                  alt="Vista previa de tu foto"
                  className="h-40 w-32 rounded-lg border border-black/10 object-cover"
                />
              )}
            </div>
          </section>

          <button
            type="submit"
            className="btn-primary"
            disabled={submitting || origen === null || photo === null}
          >
            {submitting ? 'Enviando…' : 'Generar la prueba'}
          </button>

          {(origen === null || photo === null) && (
            <p className="text-xs text-ink-muted">
              Elige una prenda y sube una foto para continuar.
            </p>
          )}
        </form>
      )}

      {session !== null && (
        <section className="space-y-5">
          {isRunning && (
            <>
              <LoadingBlock
                label={
                  session.status === 'pending'
                    ? 'En cola…'
                    : 'Generando el resultado…'
                }
              />
              <p className="text-center text-xs text-ink-muted">
                Puedes esperar aqui. La prueba tambien quedara guardada en{' '}
                <Link to="/mis-pruebas" className="underline underline-offset-2">
                  Mis pruebas
                </Link>
                .
              </p>
            </>
          )}

          {session.status === 'failed' && (
            <ErrorBlock
              title="No se pudo generar la prueba"
              detail={session.error_message ?? 'Error desconocido.'}
              action={
                <button type="button" className="btn-ghost" onClick={reset}>
                  Probar otra vez
                </button>
              }
            />
          )}

          {session.status === 'completed' && session.output_image_url && (
            <>
              <h2 className="font-display text-xl">Resultado</h2>
              <div className="grid gap-5 sm:grid-cols-2">
                <figure className="card overflow-hidden">
                  <img
                    src={session.input_image_url ?? ''}
                    alt="Tu foto original"
                    className="w-full object-cover"
                  />
                  <figcaption className="px-4 py-3 text-xs text-ink-muted">
                    Tu foto
                  </figcaption>
                </figure>
                <figure className="card overflow-hidden">
                  <img
                    src={session.output_image_url}
                    alt="Resultado de la prueba virtual"
                    className="w-full object-cover"
                  />
                  <figcaption className="px-4 py-3 text-xs text-ink-muted">
                    Resultado · generado por {session.provider ?? 'desconocido'}
                  </figcaption>
                </figure>
              </div>
              <button type="button" className="btn-ghost" onClick={reset}>
                Probar otra prenda
              </button>
            </>
          )}
        </section>
      )}
    </div>
  )
}

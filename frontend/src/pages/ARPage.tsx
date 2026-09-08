/**
 * Probador con camara en vivo (Fase 5).
 *
 * COMO ENCAJA CON LO QUE YA HABIA
 * -------------------------------
 * La parte de camara es nueva y corre entera en el navegador. La captura NO
 * lo es: al pulsar el boton se manda el fotograma a `POST /api/try-on-sessions`
 * exactamente igual que la pantalla del probador de siempre, y de ahi en
 * adelante es el mismo camino de sondeo y resultado.
 *
 * O sea que el dia que se conecte el modelo de IA de verdad, esta pantalla se
 * beneficia sin tocar una linea: el proveedor esta detras de `TryOnProvider`.
 *
 * LO QUE SE VE Y LO QUE NO
 * ------------------------
 * En vivo se ve un bosquejo: tu silueta recortada, tu esqueleto y la prenda
 * superpuesta y girada con tus hombros. Es una superposicion rigida, no una
 * simulacion de tela.
 *
 * El resultado realista aparece al capturar, y lo genera el modelo. Esa es la
 * division deliberada: el navegador da la interaccion en tiempo real y gratis,
 * el modelo da el realismo cuando lo pides.
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'

import { usePoseScanner } from '@/ar/usePoseScanner'
import { dibujarEsqueleto, dibujarPrenda, dibujarSilueta, medirCuerpo } from '@/ar/overlay'
import { removeBackground } from '@/ar/removeBackground'
import type { RecorteResultado } from '@/ar/removeBackground'
import { ErrorBlock, LoadingBlock } from '@/components/StateBlocks'
import { useApi } from '@/hooks/useApi'
import {
  createTryOnSession,
  fetchDesigns,
  fetchGarments,
  fetchTryOnSession,
} from '@/services/endpoints'
import type { Design, Garment, TryOnSession } from '@/types'

const COLOR_SILUETA: [number, number, number] = [124, 58, 237]
const COLOR_ESQUELETO = '#22d3ee'
const POLL_INTERVAL_MS = 2000
const POLL_TIMEOUT_MS = 120_000

type Origen = { tipo: 'catalogo'; id: number; url: string } | { tipo: 'diseno'; id: number; url: string }

export default function ARPage() {
  const { videoRef, status, error: errorCamara, frame, start, stop } = usePoseScanner()

  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const prendaRef = useRef<RecorteResultado | null>(null)

  const garmentsFetcher = useCallback((s: AbortSignal) => fetchGarments({ signal: s }), [])
  const { data: garments } = useApi(garmentsFetcher)
  const designsFetcher = useCallback((s: AbortSignal) => fetchDesigns(s), [])
  const { data: designs } = useApi(designsFetcher)

  const [origen, setOrigen] = useState<Origen | null>(null)
  const [prendaLista, setPrendaLista] = useState(false)
  const [sesion, setSesion] = useState<TryOnSession | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [capturando, setCapturando] = useState(false)

  const vestibles = (garments ?? []).filter((g: Garment) => g.image_url !== null)
  const disenosListos = (designs ?? []).filter(
    (d: Design) => d.status === 'completed' && d.image_url !== null,
  )

  // Recorte del fondo de la prenda elegida. Se hace una sola vez por prenda y
  // se guarda: recortar cuesta recorrer la imagen entera y no puede repetirse
  // en cada fotograma.
  useEffect(() => {
    if (origen === null) {
      prendaRef.current = null
      setPrendaLista(false)
      return
    }

    let activo = true
    let objectUrl: string | null = null
    setPrendaLista(false)

    // POR QUE FETCH Y NO `new Image()` CON crossOrigin
    // ------------------------------------------------
    // `removeBackground` necesita leer los pixeles, y para eso la imagen no
    // puede "contaminar" el canvas: tiene que venir con CORS.
    //
    // Pero poner `img.crossOrigin = 'anonymous'` NO basta, y falla de una
    // forma que cuesta encontrar: el navegador guarda en cache si una imagen
    // se pidio con CORS o sin el. El selector de prendas de esta misma
    // pantalla ya la ha mostrado en un <img> normal, o sea SIN CORS. Cuando
    // despues se pide la misma URL con CORS, el navegador encuentra la
    // entrada cacheada sin CORS, la rechaza, y dispara `onerror` -- aunque el
    // servidor mande las cabeceras correctas y aunque recargando funcione.
    //
    // Descargandola con `fetch` y convirtiendola en un blob, la imagen pasa a
    // ser del MISMO origen (`blob:`), asi que nunca contamina el canvas.
    //
    // `cache: 'reload'` NO es opcional, y costo encontrarlo: `fetch` comparte
    // la cache HTTP con las <img> de la pagina, asi que se encuentra la misma
    // entrada guardada sin cabeceras CORS y falla con un escueto "Failed to
    // fetch". Medido en el navegador: la misma URL da error tal cual, y HTTP
    // 200 con `cache: 'reload'` o con un parametro anti-cache.
    //
    // No basta con poner crossOrigin en las miniaturas de ESTA pantalla: el
    // catalogo y el probador muestran las mismas imagenes sin CORS, asi que
    // basta con haber pasado por ahi antes para envenenar la cache. Forzar la
    // recarga funciona siempre, y el coste es una descarga por prenda elegida.
    fetch(origen.url, { mode: 'cors', cache: 'reload' })
      .then((respuesta) => {
        if (!respuesta.ok) throw new Error(`El servidor respondio ${respuesta.status}.`)
        return respuesta.blob()
      })
      .then(
        (blob) =>
          new Promise<HTMLImageElement>((resolve, reject) => {
            const img = new Image()
            objectUrl = URL.createObjectURL(blob)
            img.onload = () => resolve(img)
            img.onerror = () => reject(new Error('El archivo no es una imagen valida.'))
            img.src = objectUrl
          }),
      )
      .then((img) => {
        if (!activo) return
        prendaRef.current = removeBackground(img)
        setPrendaLista(true)
      })
      .catch((causa: unknown) => {
        if (!activo) return
        setError(
          causa instanceof Error
            ? `No se pudo preparar la prenda: ${causa.message}`
            : 'No se pudo preparar la prenda.',
        )
      })
      .finally(() => {
        // El blob se libera SIEMPRE: ya se ha volcado a un canvas y mantener
        // la URL viva solo retendria memoria.
        if (objectUrl !== null) URL.revokeObjectURL(objectUrl)
      })

    return () => {
      activo = false
    }
  }, [origen])

  // Bucle de dibujo. Separado del bucle de deteccion a proposito: la deteccion
  // la marca MediaPipe y el dibujo lo marca el navegador.
  useEffect(() => {
    const canvas = canvasRef.current
    const video = videoRef.current
    if (canvas === null || video === null || frame === null) return

    const ctx = canvas.getContext('2d')
    if (ctx === null) return

    ctx.clearRect(0, 0, canvas.width, canvas.height)

    if (frame.mask !== null) {
      ctx.globalAlpha = 0.35
      dibujarSilueta(ctx, frame.mask, frame.maskWidth, frame.maskHeight, COLOR_SILUETA)
      ctx.globalAlpha = 1
    }

    const medidas = medirCuerpo(frame.landmarks, canvas.width, canvas.height)

    if (medidas !== null && prendaRef.current !== null) {
      dibujarPrenda(ctx, prendaRef.current.canvas, prendaRef.current.bounds, medidas)
    }

    dibujarEsqueleto(ctx, frame.landmarks, canvas.width, canvas.height, COLOR_ESQUELETO)
  }, [frame, videoRef])

  // Sondeo del resultado, igual que en el probador de siempre.
  const enCurso = sesion?.status === 'pending' || sesion?.status === 'processing'
  const iniciado = useRef(0)
  useEffect(() => {
    if (sesion === null || !enCurso) return
    if (iniciado.current === 0) iniciado.current = Date.now()

    const controller = new AbortController()
    let activo = true
    const timer = window.setInterval(async () => {
      if (Date.now() - iniciado.current > POLL_TIMEOUT_MS) {
        window.clearInterval(timer)
        if (activo) setError('La prueba esta tardando demasiado.')
        return
      }
      try {
        const actual = await fetchTryOnSession(sesion.id, controller.signal)
        if (activo) setSesion(actual)
      } catch {
        // Un corte puntual no debe abortar el sondeo.
      }
    }, POLL_INTERVAL_MS)

    return () => {
      activo = false
      controller.abort()
      window.clearInterval(timer)
    }
  }, [sesion, enCurso])

  const dimensionarCanvas = useCallback(() => {
    const canvas = canvasRef.current
    const video = videoRef.current
    if (canvas === null || video === null || video.videoWidth === 0) return
    // Resolucion real del video, no la que le da el CSS: mezclarlas deforma
    // todo lo que se pinte encima.
    canvas.width = video.videoWidth
    canvas.height = video.videoHeight
  }, [videoRef])

  async function capturar() {
    const video = videoRef.current
    if (video === null || origen === null) return

    setError(null)
    setCapturando(true)
    iniciado.current = 0

    try {
      // Se captura el fotograma LIMPIO, sin el bosquejo ni la prenda
      // superpuesta encima. Al modelo hay que darle la foto de la persona, no
      // una foto con dibujos: los tomaria como parte de la imagen.
      const captura = document.createElement('canvas')
      captura.width = video.videoWidth
      captura.height = video.videoHeight
      captura.getContext('2d')?.drawImage(video, 0, 0)

      const blob = await new Promise<Blob | null>((resolve) =>
        captura.toBlob(resolve, 'image/png'),
      )
      if (blob === null) throw new Error('No se pudo capturar el fotograma.')

      const foto = new File([blob], 'captura.png', { type: 'image/png' })
      setSesion(
        await createTryOnSession(
          origen.tipo === 'catalogo' ? { garmentId: origen.id } : { designId: origen.id },
          foto,
        ),
      )
    } catch (causa) {
      setError(causa instanceof Error ? causa.message : 'No se pudo capturar.')
    } finally {
      setCapturando(false)
    }
  }

  const escaneando = status === 'scanning'
  const hayPersona = frame !== null

  return (
    <div className="max-w-5xl space-y-8">
      <header>
        <h1 className="font-display text-3xl">Probador con camara</h1>
        <p className="mt-1.5 text-sm text-ink-muted">
          Ponte delante de la camara, elige una prenda y captura para ver el resultado.
        </p>
      </header>

      <div className="card border-sky-200 bg-sky-50/60 px-5 py-4 text-sm text-sky-900">
        <strong className="font-medium">Tu camara no sale de tu equipo.</strong> La deteccion
        del cuerpo corre entera en tu navegador y no se envia nada al servidor. Solo viaja
        una fotografia cuando pulsas Capturar.
      </div>

      {(error || errorCamara) && (
        <ErrorBlock title="Algo ha fallado" detail={error ?? errorCamara ?? ''} />
      )}

      <section className="space-y-3">
        <h2 className="font-display text-xl">1. Elige una prenda</h2>

        {vestibles.length === 0 && disenosListos.length === 0 && (
          <p className="text-sm text-ink-muted">
            No hay prendas con imagen todavia.{' '}
            <Link to="/catalogo" className="underline underline-offset-2">
              Ver el catalogo
            </Link>
            .
          </p>
        )}

        <ul className="grid grid-cols-3 gap-3 sm:grid-cols-5 lg:grid-cols-7">
          {[
            ...disenosListos.map((d) => ({
              key: `d${d.id}`,
              o: { tipo: 'diseno' as const, id: d.id, url: d.image_url as string },
              nombre: d.prompt,
            })),
            ...vestibles.map((g) => ({
              key: `g${g.id}`,
              o: { tipo: 'catalogo' as const, id: g.id, url: g.image_url as string },
              nombre: g.name,
            })),
          ].map(({ key, o, nombre }) => {
            const elegida = origen?.tipo === o.tipo && origen.id === o.id
            return (
              <li key={key}>
                <button
                  type="button"
                  onClick={() => setOrigen(o)}
                  aria-pressed={elegida}
                  title={nombre}
                  className={`card w-full overflow-hidden transition ${
                    elegida ? 'ring-2 ring-accent' : 'hover:border-black/20'
                  }`}
                >
                  <div className="aspect-square bg-canvas">
                    <img src={o.url} alt={nombre} className="h-full w-full object-contain" />
                  </div>
                </button>
              </li>
            )
          })}
        </ul>
      </section>

      <section className="space-y-3">
        <h2 className="font-display text-xl">2. Ponte delante de la camara</h2>

        <div className="relative overflow-hidden rounded-xl2 border border-black/[0.07] bg-ink">
          {/* `-scale-x-100`: efecto espejo. Sin el, moverte a la derecha te
              mueve a la izquierda en pantalla y resulta desconcertante. */}
          <video
            ref={videoRef}
            playsInline
            muted
            // El canvas se dimensiona AQUI y no en el bucle de dibujo: aquel
            // solo corre cuando hay una persona detectada, asi que mientras no
            // te viera, el canvas se quedaba en su tamano por defecto (300x150)
            // y el CSS lo estiraba. Los metadatos del video llegan siempre.
            onLoadedMetadata={dimensionarCanvas}
            className="w-full -scale-x-100"
            style={{ display: escaneando ? 'block' : 'none' }}
          />
          <canvas
            ref={canvasRef}
            className="pointer-events-none absolute inset-0 h-full w-full -scale-x-100"
            style={{ display: escaneando ? 'block' : 'none' }}
          />

          {!escaneando && (
            <div className="flex aspect-video items-center justify-center p-8 text-center">
              {status === 'idle' && (
                <button type="button" className="btn-primary" onClick={start}>
                  Encender la camara
                </button>
              )}
              {(status === 'loading' || status === 'requesting-camera') && (
                <div className="text-sm text-white/80">
                  <LoadingBlock
                    label={
                      status === 'loading'
                        ? 'Cargando el modelo (unos 28 MB la primera vez)…'
                        : 'Esperando permiso de la camara…'
                    }
                  />
                </div>
              )}
              {status === 'error' && (
                <button type="button" className="btn-ghost bg-white" onClick={start}>
                  Reintentar
                </button>
              )}
            </div>
          )}
        </div>

        {escaneando && (
          <div className="flex flex-wrap items-center gap-3">
            <span
              className={`pill ${
                hayPersona ? 'bg-green-100 text-green-900' : 'bg-amber-100 text-amber-900'
              }`}
            >
              {hayPersona ? 'Persona detectada' : 'No te veo: apartate para salir entero'}
            </span>
            {origen !== null && !prendaLista && (
              <span className="pill bg-black/[0.05] text-ink-muted">Recortando la prenda…</span>
            )}
            <button type="button" className="btn-ghost px-3.5 py-1.5" onClick={stop}>
              Apagar la camara
            </button>
          </div>
        )}
      </section>

      {escaneando && (
        <section className="space-y-3">
          <h2 className="font-display text-xl">3. Captura el resultado</h2>
          <p className="text-sm text-ink-muted">
            La superposicion de arriba es una vista previa rigida. Al capturar, el modelo
            genera la version realista.
          </p>
          <button
            type="button"
            className="btn-primary"
            onClick={capturar}
            disabled={capturando || enCurso || origen === null || !hayPersona}
          >
            {capturando ? 'Enviando…' : 'Capturar y generar'}
          </button>
          {origen === null && (
            <p className="text-xs text-ink-muted">Elige una prenda para poder capturar.</p>
          )}
        </section>
      )}

      {sesion !== null && (
        <section className="space-y-4">
          <h2 className="font-display text-xl">Resultado</h2>

          {enCurso && <LoadingBlock label="Generando…" />}

          {sesion.status === 'failed' && (
            <ErrorBlock
              title="No se pudo generar"
              detail={sesion.error_message ?? 'Error desconocido.'}
            />
          )}

          {sesion.status === 'completed' && sesion.output_image_url && (
            <div className="grid gap-5 sm:grid-cols-2">
              <figure className="card overflow-hidden">
                <img src={sesion.input_image_url ?? ''} alt="Tu captura" className="w-full" />
                <figcaption className="px-4 py-3 text-xs text-ink-muted">Tu captura</figcaption>
              </figure>
              <figure className="card overflow-hidden">
                <img src={sesion.output_image_url} alt="Resultado" className="w-full" />
                <figcaption className="px-4 py-3 text-xs text-ink-muted">
                  Resultado · {sesion.provider ?? 'desconocido'}
                </figcaption>
              </figure>
            </div>
          )}
        </section>
      )}
    </div>
  )
}

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

import type { Avatar3D } from '@/ar/avatar3d'
import { usePoseScanner } from '@/ar/usePoseScanner'
import type { Encaje } from '@/ar/overlay'
import {
  ENCAJE_POR_DEFECTO,
  dibujarEsqueleto,
  dibujarPrenda,
  dibujarSilueta,
  medirCuerpo,
} from '@/ar/overlay'
import { removeBackground } from '@/ar/removeBackground'
import type { RecorteResultado } from '@/ar/removeBackground'
import { ErrorBlock, LoadingBlock } from '@/components/StateBlocks'
import { useApi } from '@/hooks/useApi'
import {
  createTryOnSession,
  deleteTryOnSession,
  fetchDesigns,
  fetchBodyProfile,
  fetchGarments,
  fetchTryOnSession,
} from '@/services/endpoints'
import type { BodyProfile, Design, Garment, TryOnSession } from '@/types'

const COLOR_SILUETA: [number, number, number] = [124, 58, 237]
const COLOR_ESQUELETO = '#22d3ee'
const POLL_INTERVAL_MS = 2000
const POLL_TIMEOUT_MS = 120_000

type Origen = { tipo: 'catalogo'; id: number; url: string } | { tipo: 'diseno'; id: number; url: string }

export default function ARPage() {
  const { videoRef, status, error: errorCamara, frame, start, stop } = usePoseScanner()

  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const prendaRef = useRef<RecorteResultado | null>(null)
  const canvas3dRef = useRef<HTMLCanvasElement | null>(null)
  const avatarRef = useRef<Avatar3D | null>(null)

  const garmentsFetcher = useCallback((s: AbortSignal) => fetchGarments({ signal: s }), [])
  const { data: garments } = useApi(garmentsFetcher)
  const designsFetcher = useCallback((s: AbortSignal) => fetchDesigns(s), [])
  const { data: designs } = useApi(designsFetcher)

  const [origen, setOrigen] = useState<Origen | null>(null)
  const [prendaLista, setPrendaLista] = useState(false)
  const [sesion, setSesion] = useState<TryOnSession | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [capturando, setCapturando] = useState(false)
  const [ver3d, setVer3d] = useState(true)
  const [giro, setGiro] = useState(0)
  const [perfil, setPerfil] = useState<BodyProfile | null>(null)
  const [avatarListo, setAvatarListo] = useState(false)
  const [encaje, setEncaje] = useState<Encaje>(ENCAJE_POR_DEFECTO)

  // Declarado arriba porque varios efectos dependen de el.
  const escaneando = status === 'scanning'

  const vestibles = (garments ?? []).filter((g: Garment) => g.image_url !== null)
  const disenosListos = (designs ?? []).filter(
    (d: Design) => d.status === 'completed' && d.image_url !== null,
  )

  // Medidas del perfil corporal. Son las que hacen que el maniqui tenga TUS
  // proporciones y no unas genericas. Si no hay perfil, el avatar usa unos
  // contornos por defecto y se avisa en pantalla.
  useEffect(() => {
    let activo = true
    fetchBodyProfile()
      .then((p) => {
        if (activo) setPerfil(p)
      })
      .catch(() => {
        // 404 = todavia no hay perfil. No es un error que haya que ensenar.
      })
    return () => {
      activo = false
    }
  }, [])

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

  // Ciclo de vida del avatar 3D. Import dinamico: Three.js son ~600 KB que no
  // tiene sentido cargar en quien no abra el panel 3D.
  useEffect(() => {
    if (!ver3d || !escaneando) return

    let activo = true
    let avatar: Avatar3D | null = null

    import('@/ar/avatar3d')
      .then(({ Avatar3D: Clase }) => {
        const canvas = canvas3dRef.current
        if (!activo || canvas === null) return
        avatar = new Clase(canvas)
        avatarRef.current = avatar
        setAvatarListo(true)
      })
      .catch(() => {
        if (activo) setError('No se pudo iniciar la vista 3D.')
      })

    return () => {
      activo = false
      avatar?.dispose()
      avatarRef.current = null
      setAvatarListo(false)
    }
  }, [ver3d, escaneando])

  // Las medidas y la prenda se pasan al avatar cuando cambian.
  useEffect(() => {
    avatarRef.current?.setMedidas(perfil)
  }, [perfil, avatarListo])

  useEffect(() => {
    // Se pasa tambien la caja util: sin ella, la textura llevaria los
    // margenes vacios del packshot y la prenda saldria diminuta.
    avatarRef.current?.setPrenda(
      prendaLista ? (prendaRef.current?.canvas ?? null) : null,
      prendaRef.current?.bounds,
    )
  }, [prendaLista, avatarListo])

  useEffect(() => {
    avatarRef.current?.girar(giro)
  }, [giro, avatarListo])

  // Actualizar la pose del maniqui con cada fotograma detectado.
  useEffect(() => {
    const avatar = avatarRef.current
    const canvas = canvas3dRef.current
    if (avatar === null || canvas === null || frame === null) return
    if (frame.worldLandmarks.length === 0) return

    const ancho = canvas.clientWidth
    const alto = canvas.clientHeight
    avatar.resize(ancho, alto)
    avatar.update(frame.worldLandmarks)
    avatar.render()
  }, [frame, avatarListo])

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
      dibujarPrenda(ctx, prendaRef.current.canvas, prendaRef.current.bounds, medidas, encaje)
    }

    dibujarEsqueleto(ctx, frame.landmarks, canvas.width, canvas.height, COLOR_ESQUELETO)
  }, [frame, videoRef, encaje])

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

  async function borrarPrueba(id: number) {
    try {
      await deleteTryOnSession(id)
      setSesion(null)
    } catch (causa) {
      setError(causa instanceof Error ? causa.message : 'No se pudo borrar.')
    }
  }

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
        una fotografia cuando pulsas Capturar, y <strong>esa foto se borra en cuanto se
        genera el resultado</strong>: no se guarda ninguna imagen tuya.
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

        {escaneando && origen !== null && (
          <div className="card space-y-3 p-5">
            <div>
              <h3 className="font-display text-lg">Ajustar el encaje</h3>
              <p className="text-xs text-ink-muted">
                El valor bueno depende de como este encuadrada la foto de la prenda y de tu
                complexion, asi que no hay uno que sirva para todos. Muevelos hasta que
                cuadre y dime los numeros: los dejo como valor por defecto.
              </p>
            </div>

            <label className="flex items-center gap-3 text-sm">
              <span className="w-24 shrink-0 text-ink-muted">Tamano</span>
              <input
                type="range"
                min={100}
                max={320}
                value={Math.round(encaje.ancho * 100)}
                onChange={(e) =>
                  setEncaje((v) => ({ ...v, ancho: Number(e.target.value) / 100 }))
                }
                className="w-full"
              />
              <span className="w-14 text-right text-xs tabular-nums text-ink-muted">
                {encaje.ancho.toFixed(2)}x
              </span>
            </label>

            <label className="flex items-center gap-3 text-sm">
              <span className="w-24 shrink-0 text-ink-muted">Altura</span>
              <input
                type="range"
                min={-50}
                max={50}
                value={Math.round(encaje.alto * 100)}
                onChange={(e) =>
                  setEncaje((v) => ({ ...v, alto: Number(e.target.value) / 100 }))
                }
                className="w-full"
              />
              <span className="w-14 text-right text-xs tabular-nums text-ink-muted">
                {encaje.alto >= 0 ? '+' : ''}
                {Math.round(encaje.alto * 100)}%
              </span>
            </label>

            <button
              type="button"
              className="btn-ghost px-3.5 py-1.5"
              onClick={() => setEncaje(ENCAJE_POR_DEFECTO)}
            >
              Volver a los valores por defecto
            </button>
          </div>
        )}

        {escaneando && ver3d && (
          <div className="space-y-3">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <h3 className="font-display text-lg">Tu modelo 3D</h3>
              <span className="text-xs text-ink-muted">
                {perfil
                  ? 'Con las medidas de tu perfil corporal'
                  : 'Con medidas por defecto: rellena tu perfil corporal para que sea el tuyo'}
              </span>
            </div>

            <div className="overflow-hidden rounded-xl2 border border-black/[0.07] bg-gradient-to-b from-slate-100 to-slate-200">
              {/* El canvas 3D tiene su propio tamano de dibujo, que el avatar
                  ajusta al del CSS en cada fotograma. */}
              <canvas ref={canvas3dRef} className="block h-[420px] w-full" />
            </div>

            <div className="flex flex-wrap items-center gap-4">
              <label className="flex flex-1 items-center gap-3 text-sm">
                <span className="whitespace-nowrap text-ink-muted">Girar</span>
                <input
                  type="range"
                  min={-180}
                  max={180}
                  step={1}
                  value={Math.round((giro * 180) / Math.PI)}
                  onChange={(e) => setGiro((Number(e.target.value) * Math.PI) / 180)}
                  className="w-full"
                />
                <span className="w-12 text-right text-xs tabular-nums text-ink-muted">
                  {Math.round((giro * 180) / Math.PI)}°
                </span>
              </label>
              <button
                type="button"
                className="btn-ghost px-3.5 py-1.5"
                onClick={() => setGiro(0)}
              >
                De frente
              </button>
            </div>

            <p className="text-xs text-ink-muted">
              La postura y las proporciones son tuyas. La cara no: reconstruir el rostro de
              una persona en 3D es otro problema, mucho mayor, y prefiero un maniquí neutro
              antes que fingir un parecido que no existe.
            </p>
          </div>
        )}

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
            <button
              type="button"
              className="btn-ghost px-3.5 py-1.5"
              onClick={() => setVer3d((v) => !v)}
            >
              {ver3d ? 'Ocultar el 3D' : 'Ver en 3D'}
            </button>
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
            <div className="max-w-md space-y-3">
              <figure className="card overflow-hidden">
                <img src={sesion.output_image_url} alt="Resultado" className="w-full" />
                <figcaption className="px-4 py-3 text-xs text-ink-muted">
                  Resultado · {sesion.provider ?? 'desconocido'}
                  {/* Ya no se ensena la captura original al lado: no existe.
                      Se borra en cuanto el resultado esta listo. */}
                  <span className="mt-1 block">Tu fotografia ya se ha borrado del servidor.</span>
                </figcaption>
              </figure>
              <button
                type="button"
                className="btn-ghost"
                onClick={() => borrarPrueba(sesion.id)}
              >
                Borrar tambien este resultado
              </button>
            </div>
          )}
        </section>
      )}
    </div>
  )
}

/**
 * El probador. Es la aplicación entera.
 *
 * QUÉ PASA AQUÍ Y DÓNDE
 * ---------------------
 * Todo en el navegador. `usePoseScanner` abre la cámara y pasa cada fotograma
 * por MediaPipe Pose, que devuelve los puntos del cuerpo y la silueta
 * recortada. `cuerpo.ts` convierte eso en medidas, `vestir.ts` coloca la
 * prenda encima y `dibujo.ts` pinta las guías.
 *
 * Al servidor solo se le piden dos cosas: la lista de prendas y sus
 * fotografías. Ninguna imagen tuya sale de aquí, y no porque se borre después
 * —es que nunca se envía—.
 *
 * POR QUÉ YA NO HAY BOTÓN DE CAPTURAR
 * -----------------------------------
 * Lo había: mandaba el fotograma a un modelo de IA que generaba la versión
 * realista. Se ha quitado con el resto de la IA generativa. Lo que queda es lo
 * que se ve en vivo, y eso obliga a que la superposición esté bien hecha en
 * lugar de servir de borrador para otra cosa.
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import {
  dibujarEsqueleto,
  dibujarMedidas,
  dibujarSilueta,
  siluetaParaRecortar,
} from '@/probador/dibujo'
import type { Cuerpo, Mascara, Orientacion } from '@/probador/cuerpo'
import {
  medirContorno,
  medirCuerpo,
  medirOrientacion,
  suavizarCuerpo,
  suavizarOrientacion,
} from '@/probador/cuerpo'
import type { Muelle } from '@/probador/inercia'
import { avanzarMuelle, crearMuelle } from '@/probador/inercia'
import { removeBackground } from '@/probador/removeBackground'
import { usePoseScanner } from '@/probador/usePoseScanner'
import type { Ajuste, Prenda } from '@/probador/vestir'
import {
  AJUSTE_NEUTRO,
  MUESTRAS_DE_CONTORNO,
  TEJIDOS,
  caminoDeLaPrenda,
  opacidadPorGiro,
  perfilarPrenda,
  tejidoDe,
  vestir,
} from '@/probador/vestir'
import { ErrorBlock, LoadingBlock, Notice } from '@/components/StateBlocks'
import { useApi } from '@/hooks/useApi'
import { fetchGarments } from '@/services/endpoints'
import { CATEGORY_LABELS, FABRIC_LABELS, type Garment, type GarmentFabric } from '@/types'

/** Color de las guías. Blanco sobre la imagen de la cámara: se ve siempre. */
const COLOR_GUIA = '#FFFFFF'
const COLOR_SILUETA: [number, number, number] = [255, 255, 255]

/** Opacidad de la prenda. Un punto por debajo de opaca, para que se intuya el cuerpo. */
const OPACIDAD_PRENDA = 0.94

const TELAS = Object.keys(TEJIDOS) as GarmentFabric[]

export default function ProbadorPage() {
  const { videoRef, status, error: errorCamara, frame, start, stop } = usePoseScanner()

  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const prendaRef = useRef<Prenda | null>(null)
  const cuerpoRef = useRef<Cuerpo | null>(null)
  const orientacionRef = useRef<Orientacion | null>(null)

  // El muelle que le da inercia a la prenda. Vive en un ref y se MUTA: es
  // estado de simulación que cambia treinta veces por segundo, y meterlo en el
  // estado de React repintaría la pantalla entera en cada fotograma.
  const muelleRef = useRef<Muelle>(crearMuelle())
  const ultimoInstanteRef = useRef(performance.now())

  const [parametros, setParametros] = useSearchParams()

  const fetcher = useCallback((signal: AbortSignal) => fetchGarments({ signal }), [])
  const { data: prendas } = useApi(fetcher)

  const [elegida, setElegida] = useState<Garment | null>(null)
  const [prendaLista, setPrendaLista] = useState(false)
  const [recorteDudoso, setRecorteDudoso] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [tela, setTela] = useState<GarmentFabric | null>(null)
  const [ajuste, setAjuste] = useState<Ajuste>(AJUSTE_NEUTRO)
  const [verGuias, setVerGuias] = useState(false)
  const [recortarAlCuerpo, setRecortarAlCuerpo] = useState(true)
  const [deEspaldas, setDeEspaldas] = useState(false)

  const escaneando = status === 'scanning'
  const vestibles = (prendas ?? []).filter((g) => g.image_url !== null)

  // Prenda que llega desde el catálogo (`/probador?prenda=7`). Solo se aplica
  // una vez, cuando la lista ya está cargada.
  useEffect(() => {
    const id = Number(parametros.get('prenda'))
    if (!id || elegida !== null || vestibles.length === 0) return
    const encontrada = vestibles.find((g) => g.id === id)
    if (encontrada) elegir(encontrada)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [parametros, vestibles.length])

  function elegir(prenda: Garment) {
    setElegida(prenda)
    setTela(prenda.fabric)
    setAjuste(AJUSTE_NEUTRO)
    // La URL sigue a la elección: así se puede compartir o recargar sin
    // perder la prenda.
    setParametros({ prenda: String(prenda.id) }, { replace: true })
  }

  // Recorte del fondo de la prenda elegida. Se hace una vez por prenda y se
  // guarda: recortar recorre la imagen entera y no cabe en un fotograma.
  useEffect(() => {
    if (elegida === null || elegida.image_url === null) {
      prendaRef.current = null
      setPrendaLista(false)
      setRecorteDudoso(false)
      return
    }

    let activo = true
    let objectUrl: string | null = null
    setPrendaLista(false)
    setError(null)

    // POR QUE FETCH Y NO `new Image()` CON crossOrigin
    // ------------------------------------------------
    // `removeBackground` necesita leer los pixeles, y para eso la imagen no
    // puede "contaminar" el canvas: tiene que venir con CORS.
    //
    // Pero poner `img.crossOrigin = 'anonymous'` NO basta, y falla de una
    // forma que cuesta encontrar: el navegador guarda en cache si una imagen
    // se pidio con CORS o sin el. El catalogo ya la ha mostrado en un <img>
    // normal, o sea SIN CORS. Cuando despues se pide la misma URL con CORS, el
    // navegador encuentra la entrada cacheada sin CORS, la rechaza, y dispara
    // `onerror` -- aunque el servidor mande las cabeceras correctas y aunque
    // recargando funcione.
    //
    // Descargandola con `fetch` y convirtiendola en un blob, la imagen pasa a
    // ser del MISMO origen (`blob:`), asi que nunca contamina el canvas.
    //
    // `cache: 'reload'` NO es opcional, y costo encontrarlo: `fetch` comparte
    // la cache HTTP con las <img> de la pagina, asi que se encuentra la misma
    // entrada guardada sin cabeceras CORS y falla con un escueto "Failed to
    // fetch". Medido en el navegador: la misma URL da error tal cual, y HTTP
    // 200 con `cache: 'reload'` o con un parametro anti-cache.
    fetch(elegida.image_url, { mode: 'cors', cache: 'reload' })
      .then((respuesta) => {
        if (!respuesta.ok) throw new Error(`El servidor respondió ${respuesta.status}.`)
        return respuesta.blob()
      })
      .then(
        (blob) =>
          new Promise<HTMLImageElement>((resolve, reject) => {
            const img = new Image()
            objectUrl = URL.createObjectURL(blob)
            img.onload = () => resolve(img)
            img.onerror = () => reject(new Error('El archivo no es una imagen válida.'))
            img.src = objectUrl
          }),
      )
      .then((img) => {
        if (!activo) return
        const recorte = removeBackground(img)
        prendaRef.current = {
          lienzo: recorte.canvas,
          caja: recorte.bounds,
          perfil: perfilarPrenda(recorte.canvas, recorte.bounds),
        }
        setRecorteDudoso(recorte.recorteDudoso)
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
        // la URL viva solo retendría memoria.
        if (objectUrl !== null) URL.revokeObjectURL(objectUrl)
      })

    return () => {
      activo = false
    }
  }, [elegida])

  // Bucle de dibujo. Separado del de detección a propósito: la detección la
  // marca MediaPipe y el dibujo lo marca el navegador.
  useEffect(() => {
    const canvas = canvasRef.current
    if (canvas === null || frame === null) return

    const ctx = canvas.getContext('2d')
    if (ctx === null) return

    ctx.clearRect(0, 0, canvas.width, canvas.height)

    // TIEMPO REAL TRANSCURRIDO, no un número fijo por fotograma.
    //
    // Todo lo que se mueve solo —el suavizado del cuerpo y el muelle de la
    // prenda— se integra con esto. Sin medirlo, el comportamiento queda atado
    // a la tasa de refresco: a 120 Hz la prenda respondería el doble de rápido
    // que a 60, y en un portátil que baja a 30 cuando se calienta cambiaría de
    // carácter sola.
    const ahora = performance.now()
    const dt = (ahora - ultimoInstanteRef.current) / 1000
    ultimoInstanteRef.current = ahora

    const medido = medirCuerpo(frame.landmarks, canvas.width, canvas.height)
    if (medido === null) {
      cuerpoRef.current = null
      // El muelle se desactiva: cuando la persona vuelva a aparecer, la prenda
      // se coloca donde toca en lugar de llegar volando desde donde estaba.
      muelleRef.current.activo = false
      return
    }

    const cuerpo = suavizarCuerpo(cuerpoRef.current, medido, dt)
    cuerpoRef.current = cuerpo

    const orientacion = suavizarOrientacion(
      orientacionRef.current,
      medirOrientacion(frame.worldLandmarks, frame.landmarks),
      dt,
    )
    orientacionRef.current = orientacion
    // El aviso de espaldas es estado de React porque lo pinta la interfaz, no
    // el lienzo. Se compara antes de escribir: en otro caso, cada fotograma
    // provocaría un renderizado nuevo de la pantalla entera.
    if (orientacion.deEspaldas !== deEspaldas) setDeEspaldas(orientacion.deEspaldas)

    const mascara: Mascara | null =
      frame.mask === null
        ? null
        : { datos: frame.mask, ancho: frame.maskWidth, alto: frame.maskHeight }

    if (mascara !== null && verGuias) {
      ctx.save()
      ctx.globalAlpha = 0.18
      dibujarSilueta(ctx, mascara, COLOR_SILUETA)
      ctx.restore()
    }

    // Declarado fuera para que las guías puedan enseñar el descuelgue.
    let dx = 0
    let dy = 0

    const prenda = prendaRef.current
    if (prenda !== null && elegida !== null) {
      const camino = caminoDeLaPrenda(cuerpo, elegida.category)
      const tejido = tejidoDe(tela)

      // --- Inercia ---
      //
      // El muelle persigue el punto del que CUELGA la prenda: los hombros en
      // una camiseta, la cintura en un pantalón. Ese punto es `camino[0]`, y
      // sale ya calculado de la categoría.
      //
      // Lo que se pasa a `vestir` es cuánto se ha quedado atrás el muelle
      // respecto al cuerpo. Al moverte es negativo —la tela va detrás—; al
      // parar se pasa de largo y cambia de signo, y eso es el rebote.
      const ancla = camino[0]
      avanzarMuelle(
        muelleRef.current,
        ancla.x,
        ancla.y,
        dt,
        tejido.frecuencia,
        tejido.amortiguacion,
      )

      // Tope al descuelgue. Un fallo de seguimiento —la detección salta a otra
      // persona, o te tapas un segundo— produce un objetivo lejísimos, y sin
      // tope la prenda saldría disparada fuera de la pantalla antes de que el
      // muelle tenga tiempo de recuperarse.
      const maximo = cuerpo.torso * tejido.vuelo
      dx = muelleRef.current.x - ancla.x
      dy = muelleRef.current.y - ancla.y
      const distancia = Math.hypot(dx, dy)
      if (distancia > maximo && distancia > 0) {
        dx = (dx / distancia) * maximo
        dy = (dy / distancia) * maximo
      }

      // El radio del barrido se ata al cuerpo, no a la pantalla: buscar el
      // borde de la persona a dos anchos de hombro de distancia solo sirve
      // para encontrar a otra que pase por detrás.
      const contorno =
        mascara === null
          ? null
          : medirContorno(
              mascara,
              canvas.width,
              canvas.height,
              camino,
              MUESTRAS_DE_CONTORNO,
              cuerpo.anchoHombros * 1.4,
            )

      const recorte =
        mascara !== null && recortarAlCuerpo
          ? siluetaParaRecortar(mascara, Math.max(2, mascara.ancho * 0.035))
          : null

      vestir(ctx, prenda, cuerpo, {
        categoria: elegida.category,
        tejido,
        ajuste,
        contorno,
        recorteAlCuerpo: recorte,
        // Se desvanece al girarte: de la espalda de la prenda no tenemos foto.
        opacidad: OPACIDAD_PRENDA * opacidadPorGiro(orientacion),
        desfase: { x: dx, y: dy },
        orientacion,
      })
    }

    if (verGuias) {
      dibujarEsqueleto(ctx, frame.landmarks, COLOR_GUIA)
      dibujarMedidas(ctx, [
        ['frontalidad', orientacion.frontalidad.toFixed(2)],
        ['giro', orientacion.giro.toFixed(2)],
        ['de espaldas', orientacion.deEspaldas ? 'sí' : 'no'],
        ['descuelgue', `${Math.round(Math.hypot(dx, dy))} px`],
        ['fotograma', `${Math.round(dt * 1000)} ms`],
      ])
    }
  }, [frame, elegida, tela, ajuste, verGuias, recortarAlCuerpo, deEspaldas])

  const dimensionarCanvas = useCallback(() => {
    const canvas = canvasRef.current
    const video = videoRef.current
    if (canvas === null || video === null || video.videoWidth === 0) return
    // Resolución real del vídeo, no la que le da el CSS: mezclarlas deforma
    // todo lo que se pinte encima.
    canvas.width = video.videoWidth
    canvas.height = video.videoHeight
  }, [videoRef])

  const hayPersona = frame !== null && cuerpoRef.current !== null

  return (
    <div className="wrap space-y-8">
      <header className="flex flex-wrap items-end justify-between gap-x-8 gap-y-4 border-b border-ink-10 pb-6">
        <div>
          <p className="rotulo">Probador</p>
          <h1 className="mt-3 font-display text-titulo">Pruébatelo</h1>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <span className={`pill ${hayPersona ? 'pill-solida' : ''}`}>
            <span
              className={`h-1.5 w-1.5 rounded-full ${
                hayPersona ? 'bg-paper' : 'bg-ink-40 animate-latido'
              }`}
              aria-hidden
            />
            {escaneando
              ? hayPersona
                ? 'Te veo'
                : 'Buscándote'
              : 'Cámara apagada'}
          </span>
          {escaneando && (
            <button type="button" className="btn-ghost px-4 py-1.5" onClick={stop}>
              Apagar
            </button>
          )}
        </div>
      </header>

      {(error || errorCamara) && (
        <ErrorBlock title="Algo ha fallado" detail={error ?? errorCamara ?? ''} />
      )}

      <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_340px] lg:gap-10">
        {/* --- Escenario --- */}
        <div className="space-y-4">
          <div className="relative overflow-hidden rounded-marco bg-ink">
            {/* `-scale-x-100`: efecto espejo. Sin él, moverte a la derecha te
                mueve a la izquierda en pantalla y resulta desconcertante. */}
            <video
              ref={videoRef}
              playsInline
              // `autoPlay` no es decorativo: `play()` se llama mientras el
              // elemento todavia esta oculto y el navegador puede rechazarlo.
              // Con esto, la imagen arranca igual en cuanto se hace visible.
              autoPlay
              muted
              // El canvas se dimensiona AQUÍ y no en el bucle de dibujo: aquel
              // solo corre cuando hay una persona detectada, así que mientras
              // no te viera, el canvas se quedaba en su tamaño por defecto
              // (300x150) y el CSS lo estiraba.
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
              <div className="sobre-negro flex aspect-[4/3] items-center justify-center p-8 text-center sm:aspect-video">
                {status === 'idle' && (
                  <div className="max-w-sm">
                    <h2 className="font-display text-2xl text-paper">Enciende la cámara</h2>
                    <p className="mt-2 text-sm leading-relaxed text-paper/60">
                      Apártate hasta que se te vea de la cabeza a la cadera. Cuanto más entero
                      salgas, mejor se coloca la prenda.
                    </p>
                    <button type="button" className="btn-inverso mt-6" onClick={start}>
                      Encender
                    </button>
                  </div>
                )}

                {(status === 'loading' || status === 'requesting-camera') && (
                  <div className="text-paper/70">
                    <LoadingBlock
                      label={
                        status === 'loading'
                          ? 'Cargando el modelo (unos 28 MB la primera vez)…'
                          : 'Esperando permiso de la cámara…'
                      }
                    />
                  </div>
                )}

                {status === 'error' && (
                  // El motivo se repite AQUI, aunque ya salga arriba en el
                  // bloque de error: cuando la camara no arranca, la mirada
                  // esta en el recuadro negro, no en lo de encima.
                  <div className="max-w-sm">
                    <h2 className="font-display text-2xl text-paper">
                      La cámara no ha arrancado
                    </h2>
                    <p className="mt-2 text-sm leading-relaxed text-paper/70">
                      {errorCamara ?? 'No se pudo iniciar la cámara.'}
                    </p>
                    <button type="button" className="btn-inverso mt-6" onClick={start}>
                      Reintentar
                    </button>
                  </div>
                )}
              </div>
            )}

            {escaneando && !hayPersona && (
              <p className="pointer-events-none absolute inset-x-0 bottom-4 mx-auto w-fit rounded-full bg-ink/80 px-4 py-2 text-xs text-paper backdrop-blur">
                No te veo entero: apártate de la cámara
              </p>
            )}

            {escaneando && hayPersona && deEspaldas && elegida !== null && (
              // Del reverso de la prenda no hay fotografía, así que dibujarla
              // sobre una espalda sería enseñar el pecho de la camisa por
              // detrás. Se retira y se dice por qué.
              <p className="pointer-events-none absolute inset-x-0 bottom-4 mx-auto w-fit rounded-full bg-ink/80 px-4 py-2 text-xs text-paper backdrop-blur">
                Te veo de espaldas · solo tengo la foto del frente de la prenda
              </p>
            )}
          </div>

          {escaneando && (
            <div className="flex flex-wrap gap-2">
              <Interruptor activo={verGuias} onClick={() => setVerGuias((v) => !v)}>
                Guías de detección
              </Interruptor>
              <Interruptor
                activo={recortarAlCuerpo}
                onClick={() => setRecortarAlCuerpo((v) => !v)}
              >
                Recortar a tu silueta
              </Interruptor>
            </div>
          )}
        </div>

        {/* --- Panel --- */}
        <aside className="space-y-8">
          <section>
            <div className="flex items-baseline justify-between gap-4">
              <h2 className="rotulo">Prenda</h2>
              {elegida && !prendaLista && (
                <span className="text-[11px] text-ink-40">Recortando…</span>
              )}
            </div>

            {vestibles.length === 0 ? (
              <p className="mt-3 text-sm text-ink-60">
                No hay prendas con fotografía todavía.{' '}
                <Link to="/catalogo" className="enlace">
                  Ver el catálogo
                </Link>
                .
              </p>
            ) : (
              // Con un catálogo largo, la rejilla empujaba el tejido y el
              // ajuste fuera de la pantalla. Limitada en alto, los tres
              // controles del panel caben juntos y se llega a ellos sin
              // recorrer la página entera.
              <ul className="mt-3 grid max-h-[42vh] grid-cols-4 gap-2 overflow-y-auto pr-1 lg:max-h-[300px] lg:grid-cols-3">
                {vestibles.map((prenda) => {
                  const activa = elegida?.id === prenda.id
                  return (
                    <li key={prenda.id}>
                      <button
                        type="button"
                        onClick={() => elegir(prenda)}
                        aria-pressed={activa}
                        title={prenda.name}
                        className={`block w-full overflow-hidden rounded border transition ${
                          activa
                            ? 'border-ink ring-1 ring-ink'
                            : 'border-ink-10 hover:border-ink-40'
                        }`}
                      >
                        <span className="block aspect-[3/4] bg-bone">
                          <img
                            src={prenda.image_url as string}
                            alt={prenda.name}
                            className="h-full w-full object-cover"
                          />
                        </span>
                      </button>
                    </li>
                  )
                })}
              </ul>
            )}

            {elegida && (
              <p className="mt-3 text-sm">
                <span className="font-medium">{elegida.name}</span>
                <span className="text-ink-60"> · {CATEGORY_LABELS[elegida.category]}</span>
              </p>
            )}

            {recorteDudoso && (
              <div className="mt-3">
                <Notice title="Esta fotografía se recorta mal">
                  <p>
                    La prenda es casi del mismo color que el fondo de su foto, así que al
                    separarla se rompe y se verá a tiras. No es un fallo del probador: hace
                    falta una fotografía sobre un fondo que contraste.
                  </p>
                </Notice>
              </div>
            )}
          </section>

          {elegida && (
            <section>
              <h2 className="rotulo">Tejido</h2>
              <p className="mt-2 text-xs leading-relaxed text-ink-60">
                Cambia cuánto se ciñe la prenda a tu contorno. No simula la tela: el cuero
                mantiene su forma, el punto se pega.
              </p>

              <div className="mt-3 flex flex-wrap gap-1.5">
                <BotonTela activo={tela === null} onClick={() => setTela(null)}>
                  Sin ficha
                </BotonTela>
                {TELAS.map((t) => (
                  <BotonTela key={t} activo={tela === t} onClick={() => setTela(t)}>
                    {FABRIC_LABELS[t]}
                  </BotonTela>
                ))}
              </div>

              {elegida.fabric !== null && tela !== elegida.fabric && (
                <button
                  type="button"
                  className="mt-2 text-[11px] text-ink-60 underline underline-offset-4 hover:text-ink"
                  onClick={() => setTela(elegida.fabric)}
                >
                  Volver a su tejido real ({FABRIC_LABELS[elegida.fabric]})
                </button>
              )}
            </section>
          )}

          {elegida && (
            <section>
              <h2 className="rotulo">Ajuste fino</h2>
              <p className="mt-2 text-xs leading-relaxed text-ink-60">
                El tamaño sale de tus medidas, no hay que buscarlo. Esto es para casos que
                una categoría no distingue: un abrigo largo pesa lo mismo que una chaqueta.
              </p>

              <div className="mt-4 space-y-4">
                <Deslizador
                  etiqueta="Ancho"
                  valor={ajuste.ancho}
                  min={0.7}
                  max={1.4}
                  paso={0.01}
                  formato={(v) => `${v.toFixed(2)}×`}
                  onChange={(ancho) => setAjuste((a) => ({ ...a, ancho }))}
                />
                <Deslizador
                  etiqueta="Largo"
                  valor={ajuste.largo}
                  min={0.6}
                  max={1.6}
                  paso={0.01}
                  formato={(v) => `${v.toFixed(2)}×`}
                  onChange={(largo) => setAjuste((a) => ({ ...a, largo }))}
                />
                <Deslizador
                  etiqueta="Altura"
                  valor={ajuste.alto}
                  min={-0.3}
                  max={0.3}
                  paso={0.01}
                  formato={(v) => `${v > 0 ? '+' : ''}${Math.round(v * 100)}%`}
                  onChange={(alto) => setAjuste((a) => ({ ...a, alto }))}
                />
              </div>

              <button
                type="button"
                className="mt-4 text-[11px] text-ink-60 underline underline-offset-4 hover:text-ink"
                onClick={() => setAjuste(AJUSTE_NEUTRO)}
              >
                Restablecer
              </button>
            </section>
          )}

          <Notice title="Tu cámara no sale de tu equipo">
            <p>
              La detección corre entera en tu navegador. No se envía vídeo, no se sube ninguna
              foto y no se guarda nada: al servidor solo se le piden las imágenes de las
              prendas.
            </p>
          </Notice>
        </aside>
      </div>
    </div>
  )
}

function Interruptor({
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
      className={`inline-flex items-center gap-2 rounded-full border px-3.5 py-1.5 text-xs transition ${
        activo ? 'border-ink bg-ink text-paper' : 'border-ink-20 text-ink-60 hover:border-ink'
      }`}
    >
      <span
        className={`h-1.5 w-1.5 rounded-full ${activo ? 'bg-paper' : 'bg-ink-20'}`}
        aria-hidden
      />
      {children}
    </button>
  )
}

function BotonTela({
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
      className={`rounded-full border px-3 py-1 text-xs transition ${
        activo ? 'border-ink bg-ink text-paper' : 'border-ink-10 text-ink-60 hover:border-ink'
      }`}
    >
      {children}
    </button>
  )
}

function Deslizador({
  etiqueta,
  valor,
  min,
  max,
  paso,
  formato,
  onChange,
}: {
  etiqueta: string
  valor: number
  min: number
  max: number
  paso: number
  formato: (valor: number) => string
  onChange: (valor: number) => void
}) {
  return (
    <label className="block">
      <span className="flex items-baseline justify-between text-xs">
        <span className="text-ink-60">{etiqueta}</span>
        <span className="tabular-nums text-ink">{formato(valor)}</span>
      </span>
      <input
        type="range"
        className="mt-2"
        min={min}
        max={max}
        step={paso}
        value={valor}
        onChange={(e) => onChange(Number(e.target.value))}
      />
    </label>
  )
}

/**
 * Escaner de personas con la camara.
 *
 * QUE HACE
 * --------
 * Abre la camara y pasa cada fotograma por MediaPipe Pose, que devuelve dos
 * cosas a la vez:
 *
 *   - 33 puntos del cuerpo (hombros, caderas, codos, rodillas...), en
 *     coordenadas normalizadas de 0 a 1.
 *   - Una mascara de segmentacion: que pixeles son la persona y cuales el
 *     fondo. Es lo que permite dibujar el "bosquejo" recortado.
 *
 * TODO CORRE EN EL NAVEGADOR
 * --------------------------
 * El modelo es WebAssembly y se ejecuta en la maquina del usuario. La imagen
 * de la camara NO sale de su equipo: no hay peticion al servidor, no hay
 * llamada a ninguna API, y no cuesta dinero. Ni siquiera hay un boton que
 * pueda enviarla: la unica salida que tiene el video es el canvas de al lado.
 *
 * Eso no es solo una ventaja tecnica: enviar video continuo del cuerpo de
 * alguien a un servidor seria una decision de privacidad que hay que tomar a
 * conciencia, y aqui no hace falta tomarla.
 *
 * POR QUE UN HOOK Y NO UN COMPONENTE
 * ----------------------------------
 * La camara y el modelo tienen un ciclo de vida propio —pedir permiso, cargar
 * ~28 MB de WASM y modelo, arrancar el bucle, y soltarlo todo al salir— que no
 * tiene nada que ver con como se pinte el resultado. Separandolo, la pantalla
 * decide que dibuja y el hook se ocupa de que haya algo que dibujar.
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import type {
  Landmark,
  NormalizedLandmark,
  PoseLandmarker as PoseLandmarkerType,
} from '@mediapipe/tasks-vision'

/** Rutas de los archivos que sirve Vite desde `public/`. */
const WASM_PATH = '/mediapipe/wasm'
const MODEL_PATH = '/models/pose_landmarker_lite.task'

export type ScannerStatus =
  | 'idle'
  | 'loading'
  | 'requesting-camera'
  | 'scanning'
  | 'error'

export interface PoseFrame {
  /** Los 33 puntos del cuerpo, normalizados de 0 a 1. Sirven para dibujar
   *  sobre la imagen de la camara. */
  landmarks: NormalizedLandmark[]
  /**
   * Los mismos puntos en 3D y EN METROS, con origen en el centro de las
   * caderas. Es lo que permite construir el maniqui tridimensional: la
   * postura viene ya medida en el espacio, no hay que reconstruirla.
   */
  worldLandmarks: Landmark[]
  /**
   * Mascara de la persona: un valor de 0 a 1 por pixel, en la resolucion que
   * decide el modelo (no la del video). 1 = persona.
   */
  mask: Float32Array | null
  maskWidth: number
  maskHeight: number
}

export function usePoseScanner() {
  const videoRef = useRef<HTMLVideoElement | null>(null)
  const landmarkerRef = useRef<PoseLandmarkerType | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const rafRef = useRef<number | null>(null)
  // El ultimo instante procesado. MediaPipe exige marcas de tiempo
  // estrictamente crecientes en modo VIDEO; repetir una lanza excepcion.
  const lastTimestampRef = useRef(-1)

  const [status, setStatus] = useState<ScannerStatus>('idle')
  const [error, setError] = useState<string | null>(null)
  const [frame, setFrame] = useState<PoseFrame | null>(null)

  /**
   * Suelta la camara y el modelo, SIN tocar el estado visible.
   *
   * Esta separado de `stop` por un fallo concreto y muy desconcertante: al
   * fallar el arranque se hacia `setStatus('error')` y despues `stop()`, que
   * acababa en `setStatus('idle')`. React agrupa los cambios de estado y gana
   * el ultimo, asi que el estado de error se perdia SIEMPRE: pulsabas
   * "Encender", algo fallaba, y la pantalla volvia al mismo boton como si no
   * hubiera pasado nada. Ni aparecia "Reintentar".
   *
   * Separando la limpieza del cambio de estado, cada camino decide en que
   * estado quiere quedarse y no hay orden que memorizar.
   */
  const soltarTodo = useCallback(() => {
    if (rafRef.current !== null) {
      cancelAnimationFrame(rafRef.current)
      rafRef.current = null
    }
    // Soltar la camara de verdad. Sin esto, el piloto del portatil se queda
    // encendido aunque el usuario se haya ido de la pantalla, que es una
    // forma bastante desagradable de sorprender a alguien.
    streamRef.current?.getTracks().forEach((track) => track.stop())
    streamRef.current = null
    if (videoRef.current) videoRef.current.srcObject = null
    landmarkerRef.current?.close()
    landmarkerRef.current = null
    lastTimestampRef.current = -1
    setFrame(null)
  }, [])

  const stop = useCallback(() => {
    soltarTodo()
    setStatus('idle')
  }, [soltarTodo])

  const start = useCallback(async () => {
    setError(null)
    setStatus('requesting-camera')

    try {
      // LA CAMARA PRIMERO, EL MODELO DESPUES
      // ------------------------------------
      // Antes era al reves, y se notaba: pulsabas "Encender" y pasaban varios
      // segundos cargando 28 MB de modelo ANTES de que el navegador enseñara
      // siquiera la peticion de permiso. Sin nada que responder, parecia que
      // el boton no hacia nada.
      //
      // Pidiendo la camara primero, el dialogo del navegador sale al instante.
      // Y si el permiso se deniega, nos ahorramos la descarga entera.
      if (typeof navigator === 'undefined' || !navigator.mediaDevices) {
        throw new Error('SIN_MEDIA_DEVICES')
      }

      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: 'user',
          width: { ideal: 1280 },
          height: { ideal: 720 },
        },
        audio: false,
      })
      streamRef.current = stream

      const video = videoRef.current
      if (video === null) throw new Error('No hay elemento de video donde pintar la camara.')
      video.srcObject = stream
      // `play()` puede rechazar porque el elemento todavia esta oculto
      // (`display:none` hasta que el estado pasa a "scanning"). No es motivo
      // para abortar: el elemento lleva `autoPlay`, y el bucle de deteccion
      // solo trabaja cuando `readyState` dice que ya hay imagen.
      await video.play().catch(() => undefined)

      setStatus('loading')

      // Import dinamico: son ~1 MB de JavaScript que no tiene sentido cargar
      // en quien nunca abra esta pantalla.
      const { FilesetResolver, PoseLandmarker } = await import('@mediapipe/tasks-vision')
      const fileset = await FilesetResolver.forVisionTasks(WASM_PATH)

      const crearModelo = (delegate: 'GPU' | 'CPU') =>
        PoseLandmarker.createFromOptions(fileset, {
          baseOptions: { modelAssetPath: MODEL_PATH, delegate },
          runningMode: 'VIDEO',
          numPoses: 1,
          // Da la silueta ademas de los puntos, en la misma pasada.
          outputSegmentationMasks: true,
        })

      // GPU cuando se puede: en CPU esto va a trompicones. Pero fallar del
      // todo es peor que ir lento, y la GPU no siempre esta disponible — hay
      // equipos sin aceleracion por hardware, y navegadores que la traen
      // desactivada. Sin este segundo intento, ahi el probador no arrancaba y
      // el error que salia hablaba de WebGL, que no le dice nada a nadie.
      let landmarker: PoseLandmarkerType
      try {
        landmarker = await crearModelo('GPU')
      } catch {
        landmarker = await crearModelo('CPU')
      }
      landmarkerRef.current = landmarker

      setStatus('scanning')

      const bucle = () => {
        const v = videoRef.current
        const l = landmarkerRef.current
        if (v === null || l === null) return

        // `currentTime` en milisegundos. Solo se procesa si avanzo, para no
        // repetir marca de tiempo ni gastar CPU en el mismo fotograma.
        const timestamp = v.currentTime * 1000
        if (v.readyState >= 2 && timestamp > lastTimestampRef.current) {
          lastTimestampRef.current = timestamp
          try {
            const resultado = l.detectForVideo(v, timestamp)
            const puntos = resultado.landmarks?.[0] ?? null
            const puntos3d = resultado.worldLandmarks?.[0] ?? []
            const mascara = resultado.segmentationMasks?.[0] ?? null

            setFrame(
              puntos === null
                ? null
                : {
                    landmarks: puntos,
                    worldLandmarks: puntos3d,
                    mask: mascara ? mascara.getAsFloat32Array() : null,
                    maskWidth: mascara?.width ?? 0,
                    maskHeight: mascara?.height ?? 0,
                  },
            )
            // La mascara reserva memoria en WASM y hay que devolverla a mano:
            // sin esto, el navegador se come la RAM en un par de minutos.
            mascara?.close()
          } catch {
            // Un fotograma suelto puede fallar (cambio de resolucion, camara
            // ocupada un instante). No es motivo para tumbar el bucle.
          }
        }
        rafRef.current = requestAnimationFrame(bucle)
      }
      rafRef.current = requestAnimationFrame(bucle)
    } catch (causa) {
      // `soltarTodo` y no `stop`: hay que soltar la camara, pero el estado
      // tiene que quedarse en "error" para que se vea el motivo y el boton de
      // reintentar. Ver el comentario de `soltarTodo`.
      soltarTodo()
      setError(mensajeDeError(causa))
      setStatus('error')
    }
  }, [soltarTodo])

  // Soltar la camara si el componente se desmonta con el escaner en marcha.
  useEffect(() => stop, [stop])

  return { videoRef, status, error, frame, start, stop }
}

/**
 * Traduce el error del navegador a algo que el usuario pueda accionar.
 *
 * Los nombres de `getUserMedia` son crudos ("NotAllowedError") y no dicen que
 * hacer. Cada caso tiene una solucion distinta y conviene decirla.
 */
function mensajeDeError(causa: unknown): string {
  const nombre = causa instanceof DOMException ? causa.name : ''
  const donde = typeof location === 'undefined' ? '' : ` (estas en ${location.origin})`

  // Causa muy habitual y nada evidente: el navegador solo da acceso a la
  // camara en un origen seguro. localhost cuenta como seguro; 127.0.0.1
  // tambien, pero la IP de la red local NO, y ahi `navigator.mediaDevices` ni
  // siquiera existe. Es lo que pasa al abrir la aplicacion desde el movil
  // apuntando al ordenador.
  if (causa instanceof Error && causa.message === 'SIN_MEDIA_DEVICES') {
    return (
      'El navegador no deja usar la camara en esta direccion' +
      donde +
      '. Solo la permite en localhost o por HTTPS. Abre http://localhost:5173 ' +
      'en el mismo ordenador donde corre el servidor.'
    )
  }

  if (nombre === 'NotAllowedError' || nombre === 'SecurityError') {
    return (
      'El navegador ha bloqueado la camara' +
      donde +
      '. Pulsa el icono de la camara —o el candado— en la barra de direcciones ' +
      'y permite el acceso; despues recarga la pagina. Si nunca te ha ' +
      'preguntado, es que el permiso quedo denegado de una vez anterior.'
    )
  }
  if (nombre === 'NotFoundError' || nombre === 'DevicesNotFoundError') {
    return 'No se encontro ninguna camara conectada a este equipo.'
  }
  if (nombre === 'NotReadableError' || nombre === 'TrackStartError') {
    return (
      'La camara esta ocupada por otro programa (Teams, Zoom, Meet, la app ' +
      'Camara de Windows...). Cierralo del todo e intentalo de nuevo.'
    )
  }
  if (nombre === 'OverconstrainedError') {
    return 'Tu camara no admite la resolucion que se le pide. Avisame y la bajo.'
  }
  if (nombre === 'AbortError') {
    return 'El navegador corto el acceso a la camara a mitad. Vuelve a intentarlo.'
  }

  // Lo que quede aqui casi siempre es el modelo, no la camara: WebAssembly
  // bloqueado, los archivos de MediaPipe sin servir, o un fallo al crearlo.
  const detalle = causa instanceof Error ? causa.message : String(causa)
  return `No se pudo iniciar el probador. El navegador dice: "${detalle}".`
}

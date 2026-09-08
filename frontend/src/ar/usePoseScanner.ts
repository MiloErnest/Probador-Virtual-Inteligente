/**
 * Escaner de personas con la camara (Fase 5, realidad aumentada).
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
 * llamada a ninguna API, y no cuesta dinero. Solo se envia una fotografia
 * cuando la persona pulsa el boton de capturar, y entonces va al probador de
 * siempre.
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

  const stop = useCallback(() => {
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
    setStatus('idle')
  }, [])

  const start = useCallback(async () => {
    setError(null)
    setStatus('loading')

    try {
      // Import dinamico: son ~1 MB de JavaScript que no tiene sentido cargar
      // en quien nunca abra esta pantalla.
      const { FilesetResolver, PoseLandmarker } = await import('@mediapipe/tasks-vision')

      const fileset = await FilesetResolver.forVisionTasks(WASM_PATH)
      const landmarker = await PoseLandmarker.createFromOptions(fileset, {
        baseOptions: {
          modelAssetPath: MODEL_PATH,
          // GPU cuando se puede: en CPU esto va a trompicones.
          delegate: 'GPU',
        },
        runningMode: 'VIDEO',
        numPoses: 1,
        // Da la silueta ademas de los puntos, en la misma pasada.
        outputSegmentationMasks: true,
      })
      landmarkerRef.current = landmarker

      setStatus('requesting-camera')
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
      await video.play()

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
      setStatus('error')
      setError(mensajeDeError(causa))
      stop()
    }
  }, [stop])

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

  if (nombre === 'NotAllowedError' || nombre === 'SecurityError') {
    return (
      'No diste permiso para usar la camara. Pulsa el icono de la camara en la ' +
      'barra de direcciones del navegador y permite el acceso.'
    )
  }
  if (nombre === 'NotFoundError' || nombre === 'DevicesNotFoundError') {
    return 'No se encontro ninguna camara conectada.'
  }
  if (nombre === 'NotReadableError') {
    return 'La camara esta siendo usada por otro programa. Cierralo e intentalo de nuevo.'
  }
  if (typeof navigator !== 'undefined' && !navigator.mediaDevices) {
    // Causa muy habitual y nada evidente: fuera de localhost, el navegador
    // solo da acceso a la camara por HTTPS.
    return (
      'El navegador no permite usar la camara en esta direccion. Hace falta ' +
      'HTTPS, o abrir la aplicacion en localhost.'
    )
  }
  return causa instanceof Error ? causa.message : 'No se pudo iniciar la camara.'
}

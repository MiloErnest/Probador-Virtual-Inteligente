/**
 * Dibujo del bosquejo de la persona y colocacion de la prenda encima.
 *
 * Funciones puras sobre un canvas: no saben nada de React ni de la camara.
 * Asi la logica de "donde va la prenda" —que es la parte con matematicas y
 * la que hay que ajustar a ojo— se puede razonar y corregir sin tocar la UI.
 */

import type { NormalizedLandmark } from '@mediapipe/tasks-vision'

/**
 * Indices de los puntos que usamos, de los 33 que devuelve MediaPipe.
 * El orden lo fija el modelo; estos son los del cuerpo que nos importan.
 */
export const PUNTO = {
  NARIZ: 0,
  HOMBRO_IZQ: 11,
  HOMBRO_DER: 12,
  CODO_IZQ: 13,
  CODO_DER: 14,
  MUNECA_IZQ: 15,
  MUNECA_DER: 16,
  CADERA_IZQ: 23,
  CADERA_DER: 24,
  RODILLA_IZQ: 25,
  RODILLA_DER: 26,
  TOBILLO_IZQ: 27,
  TOBILLO_DER: 28,
} as const

/** Huesos del bosquejo. Solo el cuerpo: la cara son 11 puntos que estorban. */
const HUESOS: [number, number][] = [
  [PUNTO.HOMBRO_IZQ, PUNTO.HOMBRO_DER],
  [PUNTO.HOMBRO_IZQ, PUNTO.CODO_IZQ],
  [PUNTO.CODO_IZQ, PUNTO.MUNECA_IZQ],
  [PUNTO.HOMBRO_DER, PUNTO.CODO_DER],
  [PUNTO.CODO_DER, PUNTO.MUNECA_DER],
  [PUNTO.HOMBRO_IZQ, PUNTO.CADERA_IZQ],
  [PUNTO.HOMBRO_DER, PUNTO.CADERA_DER],
  [PUNTO.CADERA_IZQ, PUNTO.CADERA_DER],
  [PUNTO.CADERA_IZQ, PUNTO.RODILLA_IZQ],
  [PUNTO.RODILLA_IZQ, PUNTO.TOBILLO_IZQ],
  [PUNTO.CADERA_DER, PUNTO.RODILLA_DER],
  [PUNTO.RODILLA_DER, PUNTO.TOBILLO_DER],
]

/** Por debajo de esto, el punto es una conjetura del modelo y no se dibuja. */
const VISIBILIDAD_MINIMA = 0.5

export interface Medidas {
  anchoHombros: number
  largoTorso: number
  /** Inclinacion de la linea de hombros, en radianes. Gira la prenda contigo. */
  anguloHombros: number
  centroHombros: { x: number; y: number }
  centroCaderas: { x: number; y: number }
}

/**
 * Convierte los puntos normalizados en medidas de pantalla.
 *
 * Devuelve null si no se ven los cuatro puntos que hacen falta (dos hombros y
 * dos caderas): sin ellos no se puede colocar nada con criterio, y es
 * preferible no dibujar a dibujar mal.
 */
export function medirCuerpo(
  landmarks: NormalizedLandmark[],
  ancho: number,
  alto: number,
): Medidas | null {
  const necesarios = [
    PUNTO.HOMBRO_IZQ,
    PUNTO.HOMBRO_DER,
    PUNTO.CADERA_IZQ,
    PUNTO.CADERA_DER,
  ]
  for (const i of necesarios) {
    const p = landmarks[i]
    if (p === undefined || (p.visibility ?? 1) < VISIBILIDAD_MINIMA) return null
  }

  const hi = aPantalla(landmarks[PUNTO.HOMBRO_IZQ], ancho, alto)
  const hd = aPantalla(landmarks[PUNTO.HOMBRO_DER], ancho, alto)
  const ci = aPantalla(landmarks[PUNTO.CADERA_IZQ], ancho, alto)
  const cd = aPantalla(landmarks[PUNTO.CADERA_DER], ancho, alto)

  const centroHombros = { x: (hi.x + hd.x) / 2, y: (hi.y + hd.y) / 2 }
  const centroCaderas = { x: (ci.x + cd.x) / 2, y: (ci.y + cd.y) / 2 }

  return {
    anchoHombros: Math.hypot(hd.x - hi.x, hd.y - hi.y),
    largoTorso: Math.hypot(centroCaderas.x - centroHombros.x, centroCaderas.y - centroHombros.y),
    anguloHombros: Math.atan2(hd.y - hi.y, hd.x - hi.x),
    centroHombros,
    centroCaderas,
  }
}

function aPantalla(p: NormalizedLandmark, ancho: number, alto: number) {
  return { x: p.x * ancho, y: p.y * alto }
}

/**
 * Pinta la silueta recortada de la persona.
 *
 * La mascara viene en la resolucion del modelo (256x256 tipicamente), no en
 * la del video, asi que se pinta pequena y se deja que el canvas la escale.
 */
export function dibujarSilueta(
  ctx: CanvasRenderingContext2D,
  mask: Float32Array,
  maskWidth: number,
  maskHeight: number,
  color: [number, number, number],
) {
  const buffer = ctx.createImageData(maskWidth, maskHeight)
  for (let i = 0; i < mask.length; i++) {
    const p = i * 4
    buffer.data[p] = color[0]
    buffer.data[p + 1] = color[1]
    buffer.data[p + 2] = color[2]
    // La mascara es continua de 0 a 1; usarla como alfa da un borde suave
    // gratis, en vez del recorte dentado de un umbral.
    buffer.data[p + 3] = mask[i] * 255
  }

  // Sin canvas intermedio no se puede escalar: putImageData ignora la
  // transformacion del contexto, escribe pixeles tal cual.
  const temporal = document.createElement('canvas')
  temporal.width = maskWidth
  temporal.height = maskHeight
  temporal.getContext('2d')?.putImageData(buffer, 0, 0)

  ctx.drawImage(temporal, 0, 0, ctx.canvas.width, ctx.canvas.height)
}

/** Pinta el esqueleto: huesos y articulaciones. */
export function dibujarEsqueleto(
  ctx: CanvasRenderingContext2D,
  landmarks: NormalizedLandmark[],
  ancho: number,
  alto: number,
  color: string,
) {
  ctx.save()
  ctx.strokeStyle = color
  ctx.fillStyle = color
  ctx.lineWidth = Math.max(2, ancho / 300)
  ctx.lineCap = 'round'

  for (const [a, b] of HUESOS) {
    const pa = landmarks[a]
    const pb = landmarks[b]
    if (pa === undefined || pb === undefined) continue
    if ((pa.visibility ?? 1) < VISIBILIDAD_MINIMA) continue
    if ((pb.visibility ?? 1) < VISIBILIDAD_MINIMA) continue

    const ia = aPantalla(pa, ancho, alto)
    const ib = aPantalla(pb, ancho, alto)
    ctx.beginPath()
    ctx.moveTo(ia.x, ia.y)
    ctx.lineTo(ib.x, ib.y)
    ctx.stroke()
  }

  const radio = Math.max(3, ancho / 220)
  for (const indice of Object.values(PUNTO)) {
    const p = landmarks[indice]
    if (p === undefined || (p.visibility ?? 1) < VISIBILIDAD_MINIMA) continue
    const i = aPantalla(p, ancho, alto)
    ctx.beginPath()
    ctx.arc(i.x, i.y, radio, 0, Math.PI * 2)
    ctx.fill()
  }
  ctx.restore()
}

/**
 * Ajuste del encaje de la prenda sobre el cuerpo.
 *
 * POR QUE ES AJUSTABLE Y NO UNA CONSTANTE
 * ---------------------------------------
 * El valor correcto depende de como este encuadrada la foto de producto —
 * cuanto margen tiene, donde cae el cuello, si la prenda es holgada— y de la
 * complexion de quien se la prueba. No hay un numero que sirva para todo, y
 * fijarlo a ojo garantiza que a alguien le quede mal.
 *
 * Los valores por defecto son un punto de partida razonable; la pantalla deja
 * corregirlos en vivo.
 */
export interface Encaje {
  /** Cuanto mas ancha que los hombros se dibuja. 1 = exactamente su ancho. */
  ancho: number
  /** Desplazamiento vertical, en multiplos del largo del torso. */
  alto: number
}

export const ENCAJE_POR_DEFECTO: Encaje = { ancho: 1.9, alto: 0 }

/**
 * Donde cae el cuello de la prenda respecto a su propia altura.
 *
 * Una foto de producto no empieza en el cuello: tiene margen arriba. Este
 * factor dice a que altura de la imagen esta el cuello, para poder anclarlo
 * en los hombros de la persona.
 */
const CUELLO_EN_LA_PRENDA = 0.1

/**
 * Superpone la prenda sobre el cuerpo detectado.
 *
 * Escala por el ancho de hombros, gira con la inclinacion de la linea de
 * hombros, y ancla el cuello de la prenda en el centro de los hombros. No
 * deforma la tela ni simula pliegues: es una superposicion rigida, y a eso
 * llega. El realismo lo pone el modelo de IA al capturar.
 */
export function dibujarPrenda(
  ctx: CanvasRenderingContext2D,
  prenda: HTMLCanvasElement,
  recorte: { x: number; y: number; width: number; height: number },
  medidas: Medidas,
  encaje: Encaje = ENCAJE_POR_DEFECTO,
) {
  if (recorte.width === 0 || recorte.height === 0) return

  const anchoDestino = medidas.anchoHombros * encaje.ancho
  const escala = anchoDestino / recorte.width
  const altoDestino = recorte.height * escala

  ctx.save()
  ctx.translate(medidas.centroHombros.x, medidas.centroHombros.y)
  ctx.rotate(medidas.anguloHombros)
  // El desplazamiento va DESPUES de rotar, para que suba y baje siguiendo el
  // eje del cuerpo y no el de la pantalla.
  ctx.translate(0, medidas.largoTorso * encaje.alto)
  // Un poco transparente: deja intuir el cuerpo debajo y hace evidente que
  // es una vista previa y no una fotografia.
  ctx.globalAlpha = 0.92
  ctx.drawImage(
    prenda,
    recorte.x,
    recorte.y,
    recorte.width,
    recorte.height,
    -anchoDestino / 2,
    -altoDestino * CUELLO_EN_LA_PRENDA,
    anchoDestino,
    altoDestino,
  )
  ctx.restore()
}

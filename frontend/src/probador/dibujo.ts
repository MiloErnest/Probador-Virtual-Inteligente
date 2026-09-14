/**
 * Lo que se pinta encima de la imagen de la camara, aparte de la prenda.
 *
 * Son tres cosas y las tres son funciones puras sobre un canvas: no saben nada
 * de React ni de la camara. La silueta y el esqueleto existen para que se vea
 * QUE esta detectando el modelo —si la prenda sale torcida, casi siempre es
 * que el modelo no te ve bien, y sin esto no habria forma de saberlo—.
 */

import type { NormalizedLandmark } from '@mediapipe/tasks-vision'

import type { Mascara } from '@/probador/cuerpo'
import { PUNTO, VISIBILIDAD_MINIMA } from '@/probador/cuerpo'

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

/**
 * Vuelca la mascara en un canvas, a su propia resolucion.
 *
 * La mascara llega como un Float32Array a la resolucion que decide el modelo
 * (256x256 normalmente), no a la del video. `putImageData` ignora la
 * transformacion del contexto y escribe pixeles tal cual, asi que no hay forma
 * de escalarla sin pasar por un canvas intermedio. Este es ese canvas, y se
 * reutiliza entre fotogramas para no reservar memoria treinta veces por
 * segundo.
 */
let lienzoMascara: HTMLCanvasElement | null = null
let lienzoDilatado: HTMLCanvasElement | null = null

function mascaraALienzo(mascara: Mascara, color: [number, number, number]): HTMLCanvasElement | null {
  if (lienzoMascara === null) lienzoMascara = document.createElement('canvas')
  if (lienzoMascara.width !== mascara.ancho || lienzoMascara.height !== mascara.alto) {
    lienzoMascara.width = mascara.ancho
    lienzoMascara.height = mascara.alto
  }

  const ctx = lienzoMascara.getContext('2d')
  if (ctx === null) return null

  const buffer = ctx.createImageData(mascara.ancho, mascara.alto)
  for (let i = 0; i < mascara.datos.length; i++) {
    const p = i * 4
    buffer.data[p] = color[0]
    buffer.data[p + 1] = color[1]
    buffer.data[p + 2] = color[2]
    // La mascara es continua de 0 a 1; usarla como alfa da un borde suave
    // gratis, en vez del recorte dentado de un umbral.
    buffer.data[p + 3] = mascara.datos[i] * 255
  }
  ctx.putImageData(buffer, 0, 0)
  return lienzoMascara
}

/** Pinta la silueta recortada de la persona. */
export function dibujarSilueta(
  ctx: CanvasRenderingContext2D,
  mascara: Mascara,
  color: [number, number, number],
): void {
  const lienzo = mascaraALienzo(mascara, color)
  if (lienzo === null) return
  ctx.drawImage(lienzo, 0, 0, ctx.canvas.width, ctx.canvas.height)
}

/**
 * Silueta engordada, para recortar contra ella lo que sobresalga de la prenda.
 *
 * POR QUE ENGORDADA Y NO LA SILUETA EXACTA
 * ----------------------------------------
 * Recortar la prenda justo por el borde del cuerpo la convertiria en pintura
 * corporal: una chaqueta holgada TIENE que sobresalir, y una camiseta ancha
 * tambien. Lo que molesta es verla flotar sobre el fondo, medio metro por
 * fuera.
 *
 * Engordando la silueta un poco antes de recortar se quita el flotar sin
 * quitar la holgura.
 *
 * COMO SE ENGORDA
 * ---------------
 * Dibujando la misma mascara ocho veces desplazada en circulo. Es una
 * dilatacion aproximada, pero se hace a la resolucion de la mascara —256x256,
 * no la del video— asi que cuesta poco y el resultado se escala despues.
 */
export function siluetaParaRecortar(mascara: Mascara, radio: number): HTMLCanvasElement | null {
  const origen = mascaraALienzo(mascara, [255, 255, 255])
  if (origen === null) return null

  if (lienzoDilatado === null) lienzoDilatado = document.createElement('canvas')
  if (lienzoDilatado.width !== mascara.ancho || lienzoDilatado.height !== mascara.alto) {
    lienzoDilatado.width = mascara.ancho
    lienzoDilatado.height = mascara.alto
  }

  const ctx = lienzoDilatado.getContext('2d')
  if (ctx === null) return null

  ctx.clearRect(0, 0, mascara.ancho, mascara.alto)
  ctx.drawImage(origen, 0, 0)
  for (let i = 0; i < 8; i++) {
    const angulo = (i / 8) * Math.PI * 2
    ctx.drawImage(origen, Math.cos(angulo) * radio, Math.sin(angulo) * radio)
  }

  return lienzoDilatado
}

/**
 * Lectura de las medidas en vivo, en una esquina.
 *
 * POR QUE EXISTE
 * --------------
 * Hay cosas de este probador que NO se pueden comprobar sin una persona
 * delante de una camara: si la tela rueda hacia el lado correcto al girarte,
 * cuanto se descuelga de verdad al moverte, o si el equipo aguanta la tasa de
 * refresco. Un numero en pantalla convierte «me parece que va al reves» en
 * «giro marca -0,4 y la tela se va a la derecha», que ya es accionable.
 *
 * Va dentro de las guias de deteccion, no a la vista de cualquiera: es una
 * herramienta de ajuste, no parte del producto.
 */
export function dibujarMedidas(
  ctx: CanvasRenderingContext2D,
  filas: [string, string][],
): void {
  const escala = ctx.canvas.width / 1280
  const tam = Math.max(11, Math.round(15 * escala))
  const alto = Math.round(tam * 1.5)
  const margen = Math.round(18 * escala)

  ctx.save()
  ctx.font = `${tam}px ui-monospace, Menlo, Consolas, monospace`
  ctx.textBaseline = 'middle'

  const ancho = Math.max(
    ...filas.map(([k, v]) => ctx.measureText(`${k}  ${v}`).width),
  ) + margen * 2

  // Fondo oscuro: sobre una camara clara, un texto blanco suelto no se lee.
  ctx.fillStyle = 'rgba(10, 10, 11, 0.66)'
  ctx.fillRect(margen, margen, ancho, alto * filas.length + margen)

  filas.forEach(([clave, valor], i) => {
    const y = margen + margen / 2 + alto * (i + 0.5)
    ctx.fillStyle = 'rgba(255, 255, 255, 0.55)'
    ctx.fillText(clave, margen * 1.6, y)
    ctx.fillStyle = '#FFFFFF'
    ctx.textAlign = 'right'
    ctx.fillText(valor, ancho, y)
    ctx.textAlign = 'left'
  })

  ctx.restore()
}

/** Pinta el esqueleto: huesos y articulaciones. */
export function dibujarEsqueleto(
  ctx: CanvasRenderingContext2D,
  landmarks: NormalizedLandmark[],
  color: string,
): void {
  const ancho = ctx.canvas.width
  const alto = ctx.canvas.height

  ctx.save()
  ctx.strokeStyle = color
  ctx.fillStyle = color
  ctx.lineWidth = Math.max(2, ancho / 340)
  ctx.lineCap = 'round'

  for (const [a, b] of HUESOS) {
    const pa = landmarks[a]
    const pb = landmarks[b]
    if (pa === undefined || pb === undefined) continue
    if ((pa.visibility ?? 1) < VISIBILIDAD_MINIMA) continue
    if ((pb.visibility ?? 1) < VISIBILIDAD_MINIMA) continue

    ctx.beginPath()
    ctx.moveTo(pa.x * ancho, pa.y * alto)
    ctx.lineTo(pb.x * ancho, pb.y * alto)
    ctx.stroke()
  }

  const radio = Math.max(3, ancho / 260)
  for (const indice of Object.values(PUNTO)) {
    const p = landmarks[indice]
    if (p === undefined || (p.visibility ?? 1) < VISIBILIDAD_MINIMA) continue
    ctx.beginPath()
    ctx.arc(p.x * ancho, p.y * alto, radio, 0, Math.PI * 2)
    ctx.fill()
  }
  ctx.restore()
}

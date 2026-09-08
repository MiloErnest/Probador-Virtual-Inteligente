/**
 * Recorta el fondo de una foto de producto para poder superponerla.
 *
 * EL PROBLEMA
 * -----------
 * Las fotos de catalogo vienen sobre un fondo liso claro. Si se superponen tal
 * cual sobre la persona, lo que se ve es un rectangulo gris tapandola.
 *
 * POR QUE RELLENO DESDE LOS BORDES Y NO UN FILTRO POR COLOR
 * ---------------------------------------------------------
 * Lo facil seria "borra todo lo que sea casi blanco". Con una camiseta BLANCA
 * sobre fondo gris claro, eso borra la camiseta.
 *
 * Aqui se parte de los bordes de la imagen —donde con certeza hay fondo— y se
 * extiende hacia dentro mientras el color siga pareciendose. Al llegar a la
 * prenda, el color cambia y la expansion se detiene. Una camiseta blanca
 * rodeada de prenda sigue intacta porque el relleno nunca llega a ella: no hay
 * camino desde el borde que no cruce el contorno.
 *
 * Es la misma idea que la varita magica de un editor de imagen.
 *
 * LIMITES CONOCIDOS
 * -----------------
 * - Un fondo con degradado fuerte o con sombra marcada deja restos.
 * - Una prenda que toque el borde de la imagen se recorta en parte.
 * - Los bordes quedan duros; no hay suavizado del canal alfa.
 *
 * Para fotos de producto sobre fondo liso, que es el caso, funciona bien. Un
 * recorte de calidad real es trabajo de un modelo de segmentacion, y no
 * merece la pena hasta que las prendas vengan de fotografia libre.
 */

/**
 * Cuanto puede alejarse un pixel del color de fondo y seguir contando como fondo.
 *
 * ESTE NUMERO SE ELIGIO MIDIENDO, NO A OJO
 * ----------------------------------------
 * El caso critico es una prenda BLANCA sobre el gris claro de un packshot.
 * Con un fondo #e8e8e8 y una camiseta #ffffff, la distancia entre ambos es
 * sqrt(3 * 23^2) = 39.8. Con la tolerancia en 42 que habia al principio, el
 * relleno cruzaba al blanco y se comia la camiseta entera.
 *
 * 24 deja margen de sobra por debajo de esa frontera y sigue absorbiendo el
 * ruido y las sombras suaves de un fondo de estudio. Si algun dia un fondo con
 * degradado fuerte deja restos, este es el numero a subir -- pero nunca por
 * encima de ~35, o las prendas blancas vuelven a desaparecer.
 */
const TOLERANCIA = 24

/** Si el fondo ocupa mas que esto, algo salio mal y se descarta el recorte. */
const MAXIMO_BORRADO = 0.92

export interface RecorteResultado {
  canvas: HTMLCanvasElement
  /** Caja que ocupa la prenda ya recortada, en pixeles del canvas. */
  bounds: { x: number; y: number; width: number; height: number }
}

/**
 * Devuelve un canvas con el fondo a transparente y la caja util de la prenda.
 *
 * La caja importa tanto como el recorte: las fotos de producto llevan mucho
 * margen vacio alrededor, y sin saber donde empieza la prenda de verdad, al
 * colocarla sobre los hombros quedaria descentrada y pequena.
 */
export function removeBackground(imagen: HTMLImageElement): RecorteResultado {
  const canvas = document.createElement('canvas')
  canvas.width = imagen.naturalWidth
  canvas.height = imagen.naturalHeight

  const ctx = canvas.getContext('2d', { willReadFrequently: true })
  if (ctx === null) {
    return { canvas, bounds: { x: 0, y: 0, width: canvas.width, height: canvas.height } }
  }

  ctx.drawImage(imagen, 0, 0)

  const { width, height } = canvas
  const datos = ctx.getImageData(0, 0, width, height)
  const px = datos.data

  // Color de referencia: la mediana de las cuatro esquinas. Con la mediana,
  // una esquina rara (una sombra, una marca de agua) no arrastra el resultado.
  const esquinas = [
    leerPixel(px, 0, 0, width),
    leerPixel(px, width - 1, 0, width),
    leerPixel(px, 0, height - 1, width),
    leerPixel(px, width - 1, height - 1, width),
  ]
  const fondo: [number, number, number] = [
    mediana(esquinas.map((c) => c[0])),
    mediana(esquinas.map((c) => c[1])),
    mediana(esquinas.map((c) => c[2])),
  ]

  // Relleno por difusion desde todo el perimetro. Se usa una pila explicita y
  // no recursion: una imagen de 1400x760 desbordaria la pila de llamadas.
  const visitado = new Uint8Array(width * height)
  const pila: number[] = []

  for (let x = 0; x < width; x++) {
    pila.push(x, x + (height - 1) * width)
  }
  for (let y = 0; y < height; y++) {
    pila.push(y * width, width - 1 + y * width)
  }

  let borrados = 0
  while (pila.length > 0) {
    const idx = pila.pop() as number
    if (visitado[idx] === 1) continue
    visitado[idx] = 1

    const p = idx * 4
    if (distancia(px[p], px[p + 1], px[p + 2], fondo) > TOLERANCIA) continue

    px[p + 3] = 0 // transparente
    borrados++

    const x = idx % width
    const y = (idx - x) / width
    if (x > 0) pila.push(idx - 1)
    if (x < width - 1) pila.push(idx + 1)
    if (y > 0) pila.push(idx - width)
    if (y < height - 1) pila.push(idx + width)
  }

  // Salvaguarda: si se ha borrado casi todo, es que la prenda tenia un color
  // muy parecido al fondo y el recorte se la ha comido. Mejor devolver la
  // imagen intacta que una silueta vacia.
  if (borrados / (width * height) > MAXIMO_BORRADO) {
    ctx.clearRect(0, 0, width, height)
    ctx.drawImage(imagen, 0, 0)
    return { canvas, bounds: { x: 0, y: 0, width, height } }
  }

  ctx.putImageData(datos, 0, 0)
  return { canvas, bounds: calcularCaja(px, width, height) }
}

function leerPixel(
  px: Uint8ClampedArray,
  x: number,
  y: number,
  width: number,
): [number, number, number] {
  const p = (x + y * width) * 4
  return [px[p], px[p + 1], px[p + 2]]
}

function distancia(r: number, g: number, b: number, ref: [number, number, number]): number {
  // Distancia euclidea en RGB. No es perceptualmente exacta —para eso haria
  // falta CIELAB—, pero sobre un fondo liso separa de sobra.
  const dr = r - ref[0]
  const dg = g - ref[1]
  const db = b - ref[2]
  return Math.sqrt(dr * dr + dg * dg + db * db)
}

function mediana(valores: number[]): number {
  const ordenados = [...valores].sort((a, b) => a - b)
  const mitad = Math.floor(ordenados.length / 2)
  return ordenados.length % 2 === 0
    ? (ordenados[mitad - 1] + ordenados[mitad]) / 2
    : ordenados[mitad]
}

/** Caja minima que contiene todo lo que quedo opaco. */
function calcularCaja(px: Uint8ClampedArray, width: number, height: number) {
  let minX = width
  let minY = height
  let maxX = -1
  let maxY = -1

  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      // Umbral y no "distinto de 0": los bordes del recorte dejan pixeles
      // casi transparentes que no deben estirar la caja.
      if (px[(x + y * width) * 4 + 3] > 24) {
        if (x < minX) minX = x
        if (x > maxX) maxX = x
        if (y < minY) minY = y
        if (y > maxY) maxY = y
      }
    }
  }

  if (maxX < 0) return { x: 0, y: 0, width, height }
  return { x: minX, y: minY, width: maxX - minX + 1, height: maxY - minY + 1 }
}

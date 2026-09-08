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
 * - Una prenda MUY cercana en color al fondo deja restos. Comprobado con la
 *   camiseta blanca real del proyecto: fondo 217,217,217 contra prenda
 *   231,230,235, solo 26 de separacion. Se recorta bien la mayor parte, pero
 *   queda una mancha de fondo a un lado. Separar eso de forma fiable ya no es
 *   cuestion de afinar umbrales: hace falta un modelo de segmentacion.
 * - El degradado suave de estudio si se resuelve, comparando cada pixel con su
 *   vecino (ver TOLERANCIA_VECINO).
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
 * Medido despues sobre las fotos reales del proyecto, el margen resulto ser
 * MUCHO mas estrecho de lo que sugeria ese calculo. En la foto de la camiseta
 * blanca el fondo es 217,217,217 y el centro de la camiseta 231,230,235: solo
 * 26 de distancia. O sea que el umbral tiene que quedar por debajo de 26, no
 * de 39.
 *
 * 18 separa bien: el fondo de esas fotos es muy uniforme (las cuatro esquinas
 * y los bordes quedan a 0-5 del color de referencia), asi que no hace falta
 * mas holgura. Subirlo por encima de 25 hace desaparecer la camiseta.
 */
const TOLERANCIA = 18

/**
 * Cuanto puede cambiar el color entre un pixel y su vecino y seguir siendo
 * el mismo fondo.
 *
 * POR QUE HACE FALTA ADEMAS DE LA TOLERANCIA GLOBAL
 * -------------------------------------------------
 * El fondo de una foto de estudio no es un gris plano: tiene un degradado
 * suave por la iluminacion. Lejos de las esquinas se aleja del color de
 * referencia mas de TOLERANCIA, el relleno se para, y quedan manchas de fondo
 * sin borrar. Se vio en dos prendas reales -- el jersey gris y la camiseta
 * blanca, las de color mas parecido al fondo.
 *
 * Comparando tambien con el pixel DESDE EL QUE se llego, el relleno puede
 * seguir un degradado suave indefinidamente, porque cada paso es pequeno. Y
 * sigue parandose en el borde de la prenda, donde el salto de color es
 * brusco. Es la diferencia entre "parecerse al fondo" y "ser continuo con el
 * fondo", y lo segundo es lo que de verdad define un fondo.
 */
const TOLERANCIA_VECINO = 11

/**
 * Cuanto puede alejarse el relleno del color de fondo original, aunque cada
 * paso individual sea pequeno.
 *
 * SIN ESTE TOPE, LA REGLA DEL VECINO SE COME LAS PRENDAS CLARAS
 * -------------------------------------------------------------
 * Con solo la continuidad local, el relleno sube por el borde SUAVE de una
 * camiseta blanca dando pasitos de menos de 11, y acaba borrandola entera.
 * Pasó exactamente eso al probarlo con la foto real: la camiseta desaparecio
 * y salto la salvaguarda.
 *
 * 20 permite seguir un degradado de estudio y corta antes de llegar a la
 * prenda: en la foto real, el punto de la camiseta mas parecido al fondo esta
 * a 26. Con el tope en 30 que se probo primero, el relleno llegaba hasta el y
 * se comia la camiseta entera.
 */
const DERIVA_MAXIMA = 20

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
  // Cada entrada lleva el indice del pixel Y el color desde el que se llego,
  // para poder aplicar la tolerancia con el vecino.
  const pila: number[] = []
  const empujar = (idx: number, r: number, g: number, b: number) => {
    pila.push(idx, r, g, b)
  }

  for (let x = 0; x < width; x++) {
    empujar(x, fondo[0], fondo[1], fondo[2])
    empujar(x + (height - 1) * width, fondo[0], fondo[1], fondo[2])
  }
  for (let y = 0; y < height; y++) {
    empujar(y * width, fondo[0], fondo[1], fondo[2])
    empujar(width - 1 + y * width, fondo[0], fondo[1], fondo[2])
  }

  let borrados = 0
  while (pila.length > 0) {
    const previoB = pila.pop() as number
    const previoG = pila.pop() as number
    const previoR = pila.pop() as number
    const idx = pila.pop() as number

    if (visitado[idx] === 1) continue
    visitado[idx] = 1

    const p = idx * 4
    const r = px[p]
    const g = px[p + 1]
    const b = px[p + 2]

    // Es fondo si se parece al color de referencia O si es continuo con el
    // pixel del que viene. Lo segundo es lo que permite seguir un degradado.
    const desviacion = distancia(r, g, b, fondo)
    const pareceFondo = desviacion <= TOLERANCIA
    const continuo =
      distancia(r, g, b, [previoR, previoG, previoB]) <= TOLERANCIA_VECINO &&
      desviacion <= DERIVA_MAXIMA
    if (!pareceFondo && !continuo) continue

    px[p + 3] = 0 // transparente
    borrados++

    const x = idx % width
    const y = (idx - x) / width
    if (x > 0) empujar(idx - 1, r, g, b)
    if (x < width - 1) empujar(idx + 1, r, g, b)
    if (y > 0) empujar(idx - width, r, g, b)
    if (y < height - 1) empujar(idx + width, r, g, b)
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

function distancia(
  r: number,
  g: number,
  b: number,
  ref: readonly [number, number, number],
): number {
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

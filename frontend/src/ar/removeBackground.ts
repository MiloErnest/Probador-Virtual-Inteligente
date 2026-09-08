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
 * - Una prenda casi del mismo color que el fondo se recorta peor. En la
 *   camiseta blanca real la separacion es de solo 26 (fondo 217,217,217
 *   contra prenda 231,230,235), y el umbral tiene que quedar por debajo.
 * - Una prenda que toque el borde de la imagen se recorta en parte.
 * - Los bordes quedan duros; no hay suavizado del canal alfa.
 *
 * Para fotos de producto sobre fondo liso, que es el caso, funciona bien. Un
 * recorte de calidad real es trabajo de un modelo de segmentacion, y no
 * merece la pena hasta que las prendas vengan de fotografia libre.
 */

/**
 * UMBRALES ADAPTATIVOS, NO FIJOS
 * ------------------------------
 * Un solo numero no vale para todas las fotos, y se comprobo en las reales:
 *
 *   - Camiseta blanca: fondo 217,217,217 contra prenda 231,230,235. Solo 26
 *     de separacion. Un umbral generoso se come la prenda a tiras.
 *   - Chaqueta negra: separacion enorme. Ahi el umbral puede ser amplio sin
 *     riesgo, y conviene que lo sea para barrer sombras.
 *
 * Asi que el umbral se calcula por imagen: se mide cuanto varia el fondo a lo
 * largo del borde —donde con certeza no hay prenda— y se deja un margen sobre
 * esa variacion. Un fondo de estudio uniforme da un umbral estrecho; uno con
 * degradado, uno mas ancho.
 */

/** Margen sobre la variacion medida del fondo. */
const FACTOR_MARGEN = 2.0

/** Suelo y techo del umbral. El techo es lo que impide comerse una prenda
 *  clara: por debajo de los 26 medidos en la camiseta blanca. */
const UMBRAL_MINIMO = 10
const UMBRAL_MAXIMO = 18

/**
 * Radio del cierre morfologico, en pixeles.
 *
 * POR QUE HACE FALTA
 * ------------------
 * Una prenda clara tiene pliegues en sombra que son casi del color del fondo.
 * Medido en la camiseta blanca real, recorriendo la fila de los hombros: la
 * tela esta a distancia 37-49 del fondo, pero los pliegues bajan a 5, 16 y 18.
 * El relleno entra por esos pliegues y TUNELA hacia dentro, dejando la prenda
 * rayada y sin trozos.
 *
 * Un cierre —dilatar y luego erosionar— sella tuneles y agujeros mas finos
 * que el radio, y deja la silueta practicamente igual. 4 basta para las
 * fotos del proyecto sin redondear los bordes de forma visible.
 */
const RADIO_CIERRE = 4

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

  // Umbral a medida de esta imagen: cuanto se desvia el fondo de su propio
  // color de referencia a lo largo del borde.
  const tolerancia = calcularUmbral(px, width, height, fondo)

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
    if (distancia(px[p], px[p + 1], px[p + 2], fondo) > tolerancia) continue

    px[p + 3] = 0
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

  // Limpieza final: quedarse SOLO con la mancha opaca mas grande.
  //
  // El relleno entra desde los bordes, asi que no alcanza las zonas de fondo
  // que quedan rodeadas por la prenda —entre un brazo y el cuerpo, por
  // ejemplo— ni las que estan separadas del borde. Esas quedaban como parches
  // sueltos, que es lo que se veia al lado de la camiseta blanca.
  //
  // La prenda es, por definicion, la region opaca mas grande de un packshot.
  // Todo lo demas sobra.
  // Orden importante: primero sellar los tuneles que abrio el relleno al
  // colarse por los pliegues, y DESPUES quitar lo que quede suelto. Al reves,
  // un fragmento de prenda separado por un tunel se tomaria por basura y se
  // borraria antes de poder reunirlo con el resto.
  cerrarHuecos(px, width, height)
  borrarRestosSueltos(px, width, height)

  ctx.putImageData(datos, 0, 0)
  return { canvas, bounds: calcularCaja(px, width, height) }
}

/**
 * Umbral para esta imagen, a partir de lo que varia su propio fondo.
 *
 * Se recorre el borde —donde con certeza no hay prenda— y se mira cuanto se
 * alejan sus pixeles del color de referencia. El umbral es esa variacion con
 * un margen, acotado para no comerse prendas claras.
 */
function calcularUmbral(
  px: Uint8ClampedArray,
  width: number,
  height: number,
  fondo: readonly [number, number, number],
): number {
  let maxima = 0
  const mirar = (x: number, y: number) => {
    const p = (x + y * width) * 4
    const d = distancia(px[p], px[p + 1], px[p + 2], fondo)
    if (d > maxima) maxima = d
  }

  // Muestreo cada pocos pixeles: recorrer el borde entero no cambia el
  // resultado y cuesta mas.
  const paso = Math.max(1, Math.floor(width / 200))
  for (let x = 0; x < width; x += paso) {
    mirar(x, 0)
    mirar(x, height - 1)
  }
  for (let y = 0; y < height; y += paso) {
    mirar(0, y)
    mirar(width - 1, y)
  }

  return Math.min(UMBRAL_MAXIMO, Math.max(UMBRAL_MINIMO, maxima * FACTOR_MARGEN))
}

/**
 * Cierre morfologico sobre el canal alfa: dilatar y luego erosionar.
 *
 * Sella los tuneles por los que se colo el relleno sin engordar la silueta,
 * porque la erosion deshace lo que la dilatacion anadio salvo donde sirvio
 * para cerrar un hueco.
 */
function cerrarHuecos(px: Uint8ClampedArray, width: number, height: number) {
  const opaco = new Uint8Array(width * height)
  for (let i = 0; i < opaco.length; i++) opaco[i] = px[i * 4 + 3] > 24 ? 1 : 0

  const dilatado = pasada(opaco, width, height, RADIO_CIERRE, true)
  const cerrado = pasada(dilatado, width, height, RADIO_CIERRE, false)

  // Solo se RESTAURA lo que el cierre marca como interior. Nunca se borra: si
  // un pixel ya era opaco, se queda, para no comerse detalles finos.
  for (let i = 0; i < cerrado.length; i++) {
    if (cerrado[i] === 1 && px[i * 4 + 3] <= 24) px[i * 4 + 3] = 255
  }
}

/**
 * Una pasada de dilatacion (max) o erosion (min) con ventana cuadrada.
 *
 * Se hace separable —primero en horizontal, luego en vertical— porque asi el
 * coste es proporcional al radio y no a su cuadrado. En una imagen de 1408x768
 * con radio 4, la diferencia es notable.
 */
function pasada(
  entrada: Uint8Array,
  width: number,
  height: number,
  radio: number,
  dilatar: boolean,
): Uint8Array {
  const intermedio = new Uint8Array(width * height)
  const salida = new Uint8Array(width * height)
  const combinar = dilatar
    ? (a: number, b: number) => (a > b ? a : b)
    : (a: number, b: number) => (a < b ? a : b)

  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      let v = entrada[x + y * width]
      for (let k = -radio; k <= radio; k++) {
        const xx = x + k
        if (xx < 0 || xx >= width) continue
        v = combinar(v, entrada[xx + y * width])
      }
      intermedio[x + y * width] = v
    }
  }

  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      let v = intermedio[x + y * width]
      for (let k = -radio; k <= radio; k++) {
        const yy = y + k
        if (yy < 0 || yy >= height) continue
        v = combinar(v, intermedio[x + yy * width])
      }
      salida[x + y * width] = v
    }
  }

  return salida
}

/** Deja solo la region opaca conectada mas grande. */
function borrarRestosSueltos(px: Uint8ClampedArray, width: number, height: number) {
  const etiqueta = new Int32Array(width * height).fill(-1)
  let mejorEtiqueta = -1
  let mejorTamano = 0
  let actual = 0

  const pila: number[] = []
  for (let inicio = 0; inicio < width * height; inicio++) {
    if (etiqueta[inicio] !== -1 || px[inicio * 4 + 3] <= 24) continue

    let tamano = 0
    pila.push(inicio)
    etiqueta[inicio] = actual

    while (pila.length > 0) {
      const idx = pila.pop() as number
      tamano++
      const x = idx % width
      const y = (idx - x) / width
      const vecinos = [
        x > 0 ? idx - 1 : -1,
        x < width - 1 ? idx + 1 : -1,
        y > 0 ? idx - width : -1,
        y < height - 1 ? idx + width : -1,
      ]
      for (const v of vecinos) {
        if (v < 0 || etiqueta[v] !== -1 || px[v * 4 + 3] <= 24) continue
        etiqueta[v] = actual
        pila.push(v)
      }
    }

    if (tamano > mejorTamano) {
      mejorTamano = tamano
      mejorEtiqueta = actual
    }
    actual++
  }

  if (mejorEtiqueta < 0) return
  for (let i = 0; i < width * height; i++) {
    if (etiqueta[i] !== mejorEtiqueta) px[i * 4 + 3] = 0
  }
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

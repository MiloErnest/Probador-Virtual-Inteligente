/**
 * Colocar la prenda sobre el cuerpo detectado.
 *
 * EL PROBLEMA QUE RESUELVE
 * ------------------------
 * Una foto de catalogo es un rectangulo plano. Pegarla girada sobre una
 * persona da lo que daba antes: una pegatina. Aqui no se pega entera, se
 * parte en franjas horizontales y cada franja se coloca por separado —con su
 * ancho, su posicion y su inclinacion— siguiendo el cuerpo.
 *
 * El resultado sigue SIN ser una simulacion de tela: no hay pliegues, ni
 * sombras, ni tension. Pero la prenda ya sigue el eje del cuerpo, se estrecha
 * y se ensancha donde lo hace la persona, y mide lo que tiene que medir.
 *
 * POR QUE FRANJAS Y NO UNA MALLA DE TRIANGULOS
 * --------------------------------------------
 * `drawImage` solo sabe dibujar rectangulos con una transformacion afin. Una
 * malla de triangulos obliga a recortar y transformar triangulo a triangulo:
 * mas codigo, mas coste por fotograma y bordes dentados en las costuras.
 *
 * Con franjas finas la aproximacion es la misma: veintiocho trapecios seguidos
 * describen una curva sin que se note el escalon, y cada uno es un `drawImage`
 * directo.
 *
 * LAS TRES DECISIONES QUE GOBIERNAN EL ENCAJE
 * -------------------------------------------
 * 1. DONDE empieza y acaba la prenda -> lo dice la categoria (`TRAMOS`). Una
 *    camiseta cuelga de los hombros y acaba bajo la cadera; un pantalon va de
 *    la cintura al tobillo. De ahi sale tambien su TAMANO: la prenda se escala
 *    para ocupar ese tramo.
 * 2. CUANTO mide de ancho a cada altura -> una mezcla entre la silueta de la
 *    propia prenda y el contorno real de la persona.
 * 3. CUANTO manda cada una de las dos -> lo dice el tejido (`TEJIDOS`).
 */

import type { Cuerpo, Orientacion, Punto } from '@/probador/cuerpo'
import { largoDelCamino, puntoEnCamino } from '@/probador/cuerpo'
import type { GarmentCategory, GarmentFabric } from '@/types'

// --- Tejidos -----------------------------------------------------------------

export interface Tejido {
  etiqueta: string
  /**
   * Cuanto se cine la prenda al contorno real.
   *
   * 0 = conserva su propia silueta, solo escalada. 1 = adopta la forma del
   * cuerpo. Un cuero se sostiene solo; un punto fino se pega. Es un solo
   * numero y no pretende ser mas: no simula la caida del tejido, decide
   * cuanto pesa la forma del cuerpo frente a la forma de la prenda.
   */
  cenido: number
  /** Cuanto mas ancha que el cuerpo cae. 1 = pegada al contorno. */
  holgura: number

  // --- Como se mueve ---
  //
  // Hasta aqui el tejido solo decidia la FORMA. Estos tres le dan masa, que es
  // la otra mitad de lo que distingue una tela de una calcomania: un cuero
  // apenas se descuelga y se para en seco; una seda va detras de ti y sigue
  // moviendose cuando tu ya has parado.

  /** Frecuencia propia, en Hz. Alta = se asienta enseguida. */
  frecuencia: number
  /**
   * Amortiguacion. 1 es el limite sin rebote; por debajo oscila al parar, por
   * encima va pastosa. Los tejidos rigidos y pesados van cerca de 1.
   */
  amortiguacion: number
  /** Cuanto se descuelga el bajo al moverte, en multiplos del torso. */
  vuelo: number
}

export const TEJIDOS: Record<GarmentFabric, Tejido> = {
  cotton: {
    etiqueta: 'Algodón',
    cenido: 0.55, holgura: 1.1,
    frecuencia: 2.2, amortiguacion: 0.55, vuelo: 0.09,
  },
  linen: {
    etiqueta: 'Lino',
    cenido: 0.45, holgura: 1.14,
    frecuencia: 2.0, amortiguacion: 0.45, vuelo: 0.12,
  },
  silk: {
    etiqueta: 'Seda',
    cenido: 0.8, holgura: 1.04,
    // La que mas vuela y la que menos se frena: se queda ondeando.
    frecuencia: 1.7, amortiguacion: 0.3, vuelo: 0.16,
  },
  wool: {
    etiqueta: 'Lana',
    cenido: 0.4, holgura: 1.13,
    frecuencia: 1.9, amortiguacion: 0.7, vuelo: 0.07,
  },
  knit: {
    etiqueta: 'Punto',
    cenido: 0.88, holgura: 1.02,
    frecuencia: 2.0, amortiguacion: 0.6, vuelo: 0.1,
  },
  denim: {
    etiqueta: 'Vaquero',
    cenido: 0.3, holgura: 1.12,
    frecuencia: 2.6, amortiguacion: 0.85, vuelo: 0.04,
  },
  leather: {
    etiqueta: 'Cuero',
    cenido: 0.18, holgura: 1.15,
    // Practicamente rigido: se mueve contigo y se para contigo.
    frecuencia: 3.0, amortiguacion: 0.95, vuelo: 0.025,
  },
  synthetic: {
    etiqueta: 'Sintético',
    cenido: 0.7, holgura: 1.06,
    frecuencia: 2.3, amortiguacion: 0.5, vuelo: 0.11,
  },
}

/**
 * Prenda sin tejido registrado.
 *
 * Valores intermedios a proposito. La alternativa —tratarla como si fuera
 * algodon— seria inventarse el dato, y la diferencia se ve en pantalla.
 */
export const TEJIDO_SIN_FICHA: Tejido = {
  etiqueta: 'Sin ficha',
  cenido: 0.5, holgura: 1.09,
  frecuencia: 2.2, amortiguacion: 0.6, vuelo: 0.08,
}

export function tejidoDe(tela: GarmentFabric | null): Tejido {
  return tela === null ? TEJIDO_SIN_FICHA : TEJIDOS[tela]
}

// --- Perfil de la prenda -----------------------------------------------------

/**
 * Silueta de la prenda, fila a fila.
 *
 * Saber solo la caja que ocupa la prenda no basta: una camiseta es estrecha en
 * el cuello, ancha en las mangas y recta en el bajo. Ese perfil es lo que
 * permite que cada franja se cina al cuerpo en la medida que le toca en vez de
 * estirarse toda por igual.
 *
 * Se calcula UNA vez por prenda, al elegirla. Recorrer la imagen entera no se
 * puede hacer en cada fotograma.
 */
export interface PerfilPrenda {
  /** Ancho ocupado en cada fila, de 0 a 1 respecto al ancho de la caja. */
  anchos: number[]
  /** Centro ocupado en cada fila, de -0.5 a 0.5 respecto al centro de la caja. */
  centros: number[]
}

export interface Caja {
  x: number
  y: number
  width: number
  height: number
}

export interface Prenda {
  lienzo: HTMLCanvasElement
  caja: Caja
  perfil: PerfilPrenda
}

/** Filas en las que se divide la prenda para medirla y para dibujarla. */
const FILAS = 28

/** Por debajo de esta cobertura, la fila esta practicamente vacia. */
const FILA_VACIA = 0.06

/**
 * Mide la prenda fila a fila leyendo su canal alfa.
 *
 * La prenda ya viene recortada (`removeBackground`), asi que "hay prenda" es
 * exactamente "el pixel no es transparente".
 *
 * SE MIDE DE BORDE A BORDE, Y SE INTENTO LO OTRO
 * ----------------------------------------------
 * Se probo a medir solo la mancha de tela que contiene el centro de la prenda,
 * para separar el torso de las mangas. Con las fotos reales del catalogo sale
 * mal, y por un motivo que no tiene arreglo desde aqui: la camiseta blanca
 * esta fotografiada sobre fondo gris claro, y el recorte le abre un agujero en
 * mitad del torso. La mancha central medida ahi es 0,38 del ancho de la caja
 * cuando el torso real ocupa 0,59. Un 35% de error, y sin ninguna senal de que
 * algo vaya mal.
 *
 * De borde a borde el agujero da igual. A cambio, la fila del pecho de un
 * jersey de manga larga incluye las mangas — pero eso ya no importa, porque
 * el TAMANO de la prenda no se decide midiendo su ancho (ver `vestir`).
 */
export function perfilarPrenda(lienzo: HTMLCanvasElement, caja: Caja): PerfilPrenda {
  const anchos = new Array<number>(FILAS).fill(0)
  const centros = new Array<number>(FILAS).fill(0)

  const ctx = lienzo.getContext('2d', { willReadFrequently: true })
  if (ctx === null || caja.width === 0 || caja.height === 0) {
    return { anchos: anchos.fill(1), centros }
  }

  const datos = ctx.getImageData(caja.x, caja.y, caja.width, caja.height).data
  const altoFila = caja.height / FILAS

  // Umbral bajo: el borde de un recorte tiene pixeles semitransparentes y son
  // prenda igualmente.
  const hayTela = (base: number, x: number) => datos[base + x * 4 + 3] > 24

  for (let f = 0; f < FILAS; f++) {
    const desdeY = Math.floor(f * altoFila)
    const hastaY = Math.max(desdeY + 1, Math.floor((f + 1) * altoFila))

    let sumaAncho = 0
    let sumaCentro = 0
    let filasConTela = 0

    for (let y = desdeY; y < hastaY && y < caja.height; y++) {
      const base = y * caja.width * 4

      let izquierda = -1
      let derecha = -1
      for (let x = 0; x < caja.width; x++) {
        if (!hayTela(base, x)) continue
        if (izquierda < 0) izquierda = x
        derecha = x
      }

      if (derecha < izquierda || izquierda < 0) continue
      sumaAncho += derecha - izquierda + 1
      sumaCentro += (izquierda + derecha) / 2
      filasConTela++
    }

    if (filasConTela === 0) continue
    anchos[f] = sumaAncho / filasConTela / caja.width
    centros[f] = sumaCentro / filasConTela / caja.width - 0.5
  }

  return { anchos, centros }
}

// --- Donde va cada prenda ----------------------------------------------------

/**
 * Tramo del cuerpo que cubre cada categoria, en multiplos del torso.
 *
 * Los numeros no son gusto personal: son donde cae esa prenda en un cuerpo. Y
 * son la pieza mas importante del modulo, porque de este tramo sale tambien el
 * tamano de la prenda. Si algo queda largo o corto, se corrige aqui.
 */
interface Tramo {
  /** Donde nace, en multiplos del torso. Negativo = por encima del ancla. */
  desde: number
  /** Cuelga de las caderas (pantalones) en vez de los hombros. */
  anclaEnCaderas: boolean
  /**
   * Punto del cuerpo donde acaba la prenda, si el modelo lo ve.
   *
   * POR QUE UN PUNTO Y NO UNA DISTANCIA
   * -----------------------------------
   * Un vestido hasta la rodilla acaba en TU rodilla, no a 1,5 torsos de tu
   * cadera. Las dos cosas coinciden en un cuerpo de proporciones medias y
   * divergen en cuanto alguien tiene las piernas largas. Con una distancia
   * fija, a esa persona el pantalon le quedaria por la espinilla.
   */
  hastaPunto: 'caderas' | 'rodillas' | 'tobillos'
  /** Cuanto sigue mas alla de ese punto, en multiplos del torso. */
  hastaExtra: number
  /**
   * Si ese punto no se ve —cosa normal con un portatil sobre la mesa—, hasta
   * donde llega por debajo de las caderas, en multiplos del torso. Es una
   * proporcion media, y por eso es el plan B y no el plan A.
   */
  hastaSinVer: number
}

const TRAMOS: Record<GarmentCategory, Tramo> = {
  // La costura del hombro queda un poco por encima de la articulacion, y una
  // camiseta tapa la cadera sin llegar al muslo.
  top: {
    desde: -0.08,
    anclaEnCaderas: false,
    hastaPunto: 'caderas',
    hastaExtra: 0.3,
    hastaSinVer: 0.3,
  },
  // Nace mas arriba que una camiseta (hombreras) y baja un poco mas.
  //
  // 0,4 es largo de CHAQUETA, que es lo que suele haber en esta categoria. Un
  // abrigo hasta la rodilla saldria corto: para eso esta el control de largo,
  // porque de la fotografia ya no se deduce (ver `vestir`).
  outerwear: {
    desde: -0.12,
    anclaEnCaderas: false,
    hastaPunto: 'caderas',
    hastaExtra: 0.4,
    hastaSinVer: 0.4,
  },
  // Hasta la rodilla: es el largo mas comun y el que el encuadre suele pillar.
  // Ajusta en el cuerpo del vestido, nunca en la falda.
  dress: {
    desde: -0.08,
    anclaEnCaderas: false,
    hastaPunto: 'rodillas',
    hastaExtra: 0.05,
    hastaSinVer: 1.45,
  },
  // La cinturilla va POR ENCIMA del punto de cadera, y las perneras llegan al
  // tobillo. Un pantalon ajusta arriba y cae recto: se mide en la cadera.
  bottom: {
    desde: -0.2,
    anclaEnCaderas: true,
    hastaPunto: 'tobillos',
    hastaExtra: 0,
    hastaSinVer: 1.9,
  },
  other: {
    desde: -0.08,
    anclaEnCaderas: false,
    hastaPunto: 'caderas',
    hastaExtra: 0.2,
    hastaSinVer: 0.2,
  },
}

function avanzar(p: Punto, eje: Punto, distancia: number): Punto {
  return { x: p.x + eje.x * distancia, y: p.y + eje.y * distancia }
}

/**
 * Camino que recorre la prenda sobre el cuerpo.
 *
 * Devuelve una polilinea, no un segmento recto: un pantalon tiene que doblar
 * por la rodilla, y una persona inclinada no es una linea vertical. Las
 * franjas se reparten despues a lo largo de este camino.
 */
function caminoDelCuerpo(cuerpo: Cuerpo, categoria: GarmentCategory): Punto[] {
  const tramo = TRAMOS[categoria]
  const origen = tramo.anclaEnCaderas ? cuerpo.caderas : cuerpo.hombros
  const inicio = avanzar(origen, cuerpo.eje, tramo.desde * cuerpo.torso)

  // 1. El esqueleto, con los puntos que el modelo ve de verdad y hasta donde
  //    llegue esta categoria. Las rodillas de un pantalon importan aunque el
  //    pantalon acabe en el tobillo: son las que hacen que doble.
  const esqueleto: Punto[] = [inicio]
  if (!tramo.anclaEnCaderas) esqueleto.push(cuerpo.caderas)

  let llegoAlPunto = tramo.hastaPunto === 'caderas'

  if (tramo.hastaPunto !== 'caderas' && cuerpo.rodillas !== null) {
    esqueleto.push(cuerpo.rodillas)
    if (tramo.hastaPunto === 'rodillas') llegoAlPunto = true
  }
  if (tramo.hastaPunto === 'tobillos' && cuerpo.tobillos !== null) {
    esqueleto.push(cuerpo.tobillos)
    llegoAlPunto = true
  }

  // 2. Hasta donde llega la prenda, medido a lo largo del cuerpo.
  const hastaCaderas = Math.hypot(cuerpo.caderas.x - inicio.x, cuerpo.caderas.y - inicio.y)
  const largo = llegoAlPunto
    ? largoDelCamino(esqueleto) + tramo.hastaExtra * cuerpo.torso
    : hastaCaderas + tramo.hastaSinVer * cuerpo.torso

  // 3. Prolongacion en la direccion del ultimo tramo. Hace falta siempre: si
  //    la prenda acaba mas abajo del ultimo punto visible —o si el ajuste
  //    manual la baja— tiene que haber camino donde apoyarla.
  const ultimo = esqueleto[esqueleto.length - 1]
  const anterior = esqueleto.length > 1 ? esqueleto[esqueleto.length - 2] : null
  const dx = anterior === null ? cuerpo.eje.x : ultimo.x - anterior.x
  const dy = anterior === null ? cuerpo.eje.y : ultimo.y - anterior.y
  const norma = Math.hypot(dx, dy) || 1
  esqueleto.push({
    x: ultimo.x + (dx / norma) * cuerpo.torso * 3,
    y: ultimo.y + (dy / norma) * cuerpo.torso * 3,
  })

  // 4. Recortado al largo exacto, para que `largoDelCamino` del resultado sea
  //    justo el tramo que cubre la prenda. Quien mida el contorno sobre este
  //    camino lo mide donde toca, sin tener que saber nada de todo esto.
  return recortarCamino(esqueleto, largo)
}

/** Devuelve el trozo inicial de la polilinea que mide `largo`. */
function recortarCamino(camino: Punto[], largo: number): Punto[] {
  const recortado: Punto[] = [camino[0]]
  let recorrido = 0

  for (let i = 1; i < camino.length; i++) {
    const dx = camino[i].x - camino[i - 1].x
    const dy = camino[i].y - camino[i - 1].y
    const tramo = Math.hypot(dx, dy)

    if (recorrido + tramo >= largo) {
      const t = tramo === 0 ? 0 : (largo - recorrido) / tramo
      recortado.push({ x: camino[i - 1].x + dx * t, y: camino[i - 1].y + dy * t })
      return recortado
    }

    recortado.push(camino[i])
    recorrido += tramo
  }

  return recortado
}

// --- El dibujo ---------------------------------------------------------------

export interface Ajuste {
  /** Correccion manual del ancho. 1 = el que se ha calculado. */
  ancho: number
  /**
   * Correccion manual del largo. 1 = el que le toca a esa categoria.
   *
   * Existe porque una categoria mete en el mismo saco prendas de largos muy
   * distintos: en "abrigos" caben una chaqueta biker y un abrigo hasta la
   * rodilla. Antes lo resolvia la proporcion de la fotografia, pero resulto
   * poco de fiar (ver `vestir`), asi que la salida es un control.
   */
  largo: number
  /** Desplazamiento manual, en multiplos del torso. 0 = donde toca. */
  alto: number
}

export const AJUSTE_NEUTRO: Ajuste = { ancho: 1, largo: 1, alto: 0 }

/**
 * Cuanto puede desviarse la medida de la mascara del ancho anatomico.
 *
 * La mascara mide la persona de verdad, pero incluye los brazos cuando estan
 * pegados al cuerpo y se rompe con fondos complicados. Limitando la
 * correccion, un fallo de segmentacion deforma un poco la prenda en lugar de
 * convertirla en una sabana.
 */
const CORRECCION_MINIMA = 0.82
const CORRECCION_MAXIMA = 1.3

/** Lienzo de trabajo, reutilizado entre fotogramas. Ver `vestir`. */
let lienzoPrenda: HTMLCanvasElement | null = null

function lienzoDeTrabajo(ancho: number, alto: number): CanvasRenderingContext2D | null {
  if (lienzoPrenda === null) lienzoPrenda = document.createElement('canvas')
  if (lienzoPrenda.width !== ancho || lienzoPrenda.height !== alto) {
    lienzoPrenda.width = ancho
    lienzoPrenda.height = alto
  }
  const ctx = lienzoPrenda.getContext('2d')
  if (ctx === null) return null

  // La prenda se dibuja SIEMPRE reducida —una foto de producto tiene mil y
  // pico pixeles de ancho y acaba ocupando doscientos y pico—, y reducir es
  // justo donde el filtrado por defecto se nota: bordes con dientes y el
  // estampado hirviendo entre fotogramas. Pedir calidad alta cuesta poco aqui
  // porque se dibuja una vez por franja, no por pixel.
  ctx.imageSmoothingEnabled = true
  ctx.imageSmoothingQuality = 'high'

  ctx.clearRect(0, 0, ancho, alto)
  return ctx
}

export interface OpcionesVestir {
  categoria: GarmentCategory
  tejido: Tejido
  ajuste: Ajuste
  /** Semianchos reales del cuerpo a lo largo del tramo, o null si no hay mascara. */
  contorno: number[] | null
  /** Silueta de la persona para recortar lo que sobresalga. Opcional. */
  recorteAlCuerpo: HTMLCanvasElement | null
  opacidad: number

  /**
   * Cuanto va la prenda por detras del cuerpo, en pixeles del lienzo.
   *
   * Lo calcula el muelle de `inercia.ts` y llega ya resuelto: aqui solo se
   * reparte. El reparto es la parte que importa —ver `perfilDeVuelo`—, porque
   * una prenda cuelga de un sitio y se descuelga por el otro.
   */
  desfase: { x: number; y: number }

  /** Hacia donde miras. Hace rodar la tela alrededor del cuerpo al girarte. */
  orientacion: Orientacion
}

/**
 * Cuanto se descuelga la prenda a cada altura, de 0 a 1.
 *
 * Una camiseta esta SUJETA por los hombros: ahi no se mueve nada, por mucho
 * que corras. El bajo, en cambio, va suelto y es el que se queda atras. Un
 * pantalon igual, sujeto por la cintura y suelto por el bajo.
 *
 * Aplicar el retraso por igual a toda la prenda la despegaria del cuerpo en
 * bloque —se veria deslizarse por encima de ti—, que es peor que no tener
 * inercia. El exponente concentra el efecto abajo: a media altura se descuelga
 * un tercio de lo que se descuelga el bajo.
 */
function perfilDeVuelo(t: number): number {
  return t * t * Math.sqrt(t)
}

/**
 * Radio del torso respecto a su anchura.
 *
 * Un torso visto desde arriba no es un circulo, es una elipse: la profundidad
 * ronda el 55-60% de la anchura. El radio que sirve para hacer rodar la
 * textura es el semieje que apunta a la camara, de ahi el 0,28 (la mitad de
 * 0,56).
 */
const RADIO_DEL_TORSO = 0.28

/**
 * A partir de que frontalidad empieza a desvanecerse la prenda.
 *
 * Tenemos una foto del FRENTE de la prenda y nada mas. Girado mas o menos 60
 * grados ya no queda frente que ensenar, y seguir pintandolo es dibujar una
 * camiseta de frente sobre un costado. Desvanecerla es lo unico honesto que se
 * puede hacer sin una foto del lado.
 */
const FRONTALIDAD_LLENA = 0.62
const FRONTALIDAD_VACIA = 0.2

/** Opacidad que le corresponde a la prenda segun lo girado que estes. */
export function opacidadPorGiro(orientacion: Orientacion): number {
  if (orientacion.deEspaldas) return 0

  const t =
    (orientacion.frontalidad - FRONTALIDAD_VACIA) / (FRONTALIDAD_LLENA - FRONTALIDAD_VACIA)
  const recortado = Math.max(0, Math.min(1, t))
  // Suavizado de Hermite: entra y sale sin esquinas. Con una rampa lineal se
  // nota el instante exacto en que empieza y termina de desvanecerse.
  return recortado * recortado * (3 - 2 * recortado)
}

/**
 * Dibuja la prenda deformada sobre el cuerpo.
 *
 * POR QUE PASA POR UN LIENZO APARTE Y NO SE PINTA DIRECTO
 * -------------------------------------------------------
 * Las franjas se solapan un pixel para que no se vea la costura entre ellas.
 * Dibujadas con transparencia directamente sobre la imagen, ese pixel se
 * pintaria dos veces y cada union apareceria como una raya mas oscura.
 *
 * En un lienzo aparte y opaco no hay doble mezcla, y la transparencia se
 * aplica una sola vez al volcarlo entero.
 */
export function vestir(
  ctx: CanvasRenderingContext2D,
  prenda: Prenda,
  cuerpo: Cuerpo,
  opciones: OpcionesVestir,
): void {
  const { caja, perfil } = prenda
  if (caja.width === 0 || caja.height === 0) return

  // De espaldas o de perfil cerrado la opacidad es cero, y entonces las 28
  // franjas, el recorte contra la silueta y el volcado del lienzo son trabajo
  // tirado. Se corta antes de empezar.
  if (opciones.opacidad <= 0.004) return

  const camino = caminoDelCuerpo(cuerpo, opciones.categoria)
  const largoDisponible = largoDelCamino(camino)
  if (largoDisponible < 1) return

  // --- Ancho del cuerpo a cada altura ---
  //
  // Dos fuentes. La anatomica interpola entre hombros y caderas y siempre
  // esta; la medida sale de la mascara y es la persona real. La segunda
  // corrige a la primera dentro de un limite.
  const anchoCuerpo: number[] = []
  for (let f = 0; f < FILAS; f++) {
    // De 0 a 1 con los dos extremos incluidos: es la misma escala con la que
    // `medirContorno` reparte sus muestras, y las dos series se indexan juntas.
    const anatomico = anchoAnatomico(cuerpo, opciones.categoria, f / (FILAS - 1))

    let ancho = anatomico
    if (opciones.contorno !== null && opciones.contorno.length === FILAS) {
      const medido = opciones.contorno[f] * 2
      if (medido > 1) {
        ancho = Math.min(
          Math.max(medido, anatomico * CORRECCION_MINIMA),
          anatomico * CORRECCION_MAXIMA,
        )
      }
    }
    anchoCuerpo.push(ancho)
  }

  const desplazamiento = opciones.ajuste.alto * cuerpo.torso

  /**
   * Ancho del cuerpo a una distancia dada del comienzo del camino.
   *
   * Se busca por distancia recorrida y no por numero de fila: el ajuste manual
   * de altura desplaza la prenda sobre el camino, y con un indice fijo cada
   * franja leeria el ancho del cuerpo donde ya no esta.
   */
  const anchoCuerpoEn = (distancia: number): number => {
    const t = Math.min(1, Math.max(0, distancia / largoDisponible))
    return anchoCuerpo[Math.round(t * (FILAS - 1))]
  }

  // --- El tamano de la prenda sale de su ALTO, no de su ancho ---
  //
  // La prenda ocupa exactamente el tramo de cuerpo que le toca: una camiseta
  // va del hombro a poco mas abajo de la cadera, y un pantalon de la cintura
  // al tobillo. El ancho es el que tenga la fotografia a esa escala.
  //
  // POR QUE NO AL REVES, QUE ES LO PRIMERO QUE SE INTENTO
  // -----------------------------------------------------
  // La version anterior escalaba igualando el ANCHO de la prenda al del
  // cuerpo. Es mas fino sobre el papel —respeta la proporcion de la foto— y
  // con las fotos reales del catalogo da resultados incoherentes:
  //
  //   - Camiseta blanca sobre fondo gris claro: el recorte le abre un agujero
  //     en el torso, la medida sale un 35% corta y la camiseta se dibujaba a
  //     mitad del muslo.
  //   - Camisa marron: las mangas tocan el torso en la foto, asi que la fila
  //     del pecho mide la prenda entera y la camisa salia por encima de la
  //     cadera.
  //
  // Las dos son la misma clase de fallo: el ancho de una fotografia de
  // producto depende de como este colocada la prenda y de que tal haya salido
  // el recorte. El alto no: una camiseta empieza en el hombro y acaba en el
  // bajo, y eso es cierto en todas las fotos.
  //
  // Al anclar por alto, un fallo de recorte deja la prenda un poco ancha o un
  // poco estrecha en lugar de descolocarla entera. Y donde entra el cuerpo de
  // verdad es en el cenido, franja a franja, que es donde tiene sentido.
  const largo = largoDisponible * opciones.ajuste.largo
  const escala = largo / caja.height

  // --- Las franjas ---
  const trabajo = lienzoDeTrabajo(ctx.canvas.width, ctx.canvas.height)
  if (trabajo === null) return

  const altoFuente = caja.height / FILAS
  const altoDestino = largo / FILAS

  // Corrimiento de la textura al girarte, en pixeles y en el eje lateral de la
  // prenda. Sale de tratar el torso como un cilindro: un punto del frente de
  // la tela, al girar el cuerpo un angulo, aparece desplazado `radio · sen()`.
  // Es lo que hace que el estampado ruede alrededor del cuerpo en vez de
  // quedarse mirando a la camara como un cartel.
  const corrimiento =
    opciones.orientacion.giro * cuerpo.anchoHombros * RADIO_DEL_TORSO

  for (let f = 0; f < FILAS; f++) {
    const t = f / FILAS
    const recorrido = t * largo + desplazamiento
    const anchoPrendaFila = perfil.anchos[f]

    // Una fila vacia —el hueco del cuello, el aire entre las perneras— no se
    // puede ajustar a nada: no hay tela que medir. Se escala como el resto.
    const factorFila =
      anchoPrendaFila < FILA_VACIA
        ? escala
        : mezclar(
            escala,
            (anchoCuerpoEn(recorrido) * opciones.tejido.holgura) /
              (anchoPrendaFila * caja.width),
            opciones.tejido.cenido,
          )

    // El ajuste manual toca SOLO el ancho. El alto ya lo decide el cuerpo, y
    // dejar que un control lo cambiara seria volver a poder descolocar la
    // prenda a mano, que es de lo que veniamos.
    const anchoFranja = caja.width * factorFila * opciones.ajuste.ancho
    const { punto: inicio, direccion } = puntoEnCamino(camino, recorrido)
    const angulo = Math.atan2(direccion.y, direccion.x) - Math.PI / 2

    // El descuelgue va en coordenadas del LIENZO y antes de rotar: la tela se
    // queda atras en la direccion en que te has movido, que es una direccion
    // del mundo. El corrimiento por giro, en cambio, va en el eje lateral de
    // la propia prenda, y por eso entra despues de rotar.
    const vuelo = perfilDeVuelo(t)
    const x = inicio.x + opciones.desfase.x * vuelo
    const y = inicio.y + opciones.desfase.y * vuelo

    // Un NaN en `translate` o `rotate` no lanza ningun error: deja el contexto
    // en un estado invalido y todo lo que se dibuje despues desaparece sin
    // explicacion. Vale mas perder una franja que el fotograma entero.
    if (!Number.isFinite(x) || !Number.isFinite(y) || !Number.isFinite(angulo)) continue
    if (!Number.isFinite(anchoFranja) || anchoFranja <= 0) continue

    trabajo.save()
    trabajo.translate(x, y)
    trabajo.rotate(angulo)
    trabajo.drawImage(
      prenda.lienzo,
      caja.x,
      caja.y + f * altoFuente,
      caja.width,
      altoFuente,
      // El centro de la fila manda, no el de la caja: una prenda fotografiada
      // descentrada quedaria torcida sobre el cuerpo.
      -anchoFranja / 2 - perfil.centros[f] * anchoFranja + corrimiento,
      0,
      anchoFranja,
      // Un pixel de mas para que no se vea la juntura con la franja siguiente.
      altoDestino + 1,
    )
    trabajo.restore()
  }

  // --- Recorte a la silueta ---
  if (opciones.recorteAlCuerpo !== null) {
    trabajo.save()
    trabajo.globalCompositeOperation = 'destination-in'
    trabajo.drawImage(opciones.recorteAlCuerpo, 0, 0, ctx.canvas.width, ctx.canvas.height)
    trabajo.restore()
  }

  ctx.save()
  ctx.globalAlpha = opciones.opacidad
  ctx.drawImage(trabajo.canvas, 0, 0)
  ctx.restore()
}

function mezclar(a: number, b: number, factor: number): number {
  return a + (b - a) * factor
}

/**
 * Ancho del cuerpo a una altura del tramo, segun proporciones.
 *
 * Es la red de seguridad: siempre existe, aunque la mascara falle o no haya.
 * El pellizco de la cintura es lo que evita que un torso se dibuje como un
 * rectangulo.
 */
function anchoAnatomico(cuerpo: Cuerpo, categoria: GarmentCategory, t: number): number {
  if (categoria === 'bottom') {
    // De la cadera al tobillo el cuerpo se estrecha mucho. Las dos perneras
    // juntas ocupan aproximadamente el ancho de cadera arriba y poco mas de un
    // tercio abajo.
    return cuerpo.anchoCaderas * mezclar(1, 0.38, t)
  }

  const cintura = cuerpo.anchoCaderas * 0.92
  const arriba = cuerpo.anchoHombros
  const abajo = categoria === 'dress' ? cuerpo.anchoCaderas * 1.05 : cuerpo.anchoCaderas

  // Hombros -> cintura -> caderas. El punto mas estrecho cae sobre el 55% del
  // torso, que es donde esta la cintura en una persona de pie.
  if (t < 0.55) return mezclar(arriba, cintura, t / 0.55)
  return mezclar(cintura, abajo, (t - 0.55) / 0.45)
}

/** Numero de muestras que hay que pedirle a `medirContorno`. */
export const MUESTRAS_DE_CONTORNO = FILAS

/**
 * Camino que va a recorrer la prenda, para medir el contorno ahi mismo.
 *
 * Se expone porque quien mide la mascara necesita saber exactamente sobre que
 * trozo del cuerpo va a caer la prenda: medir el contorno en otro sitio seria
 * ajustar la camiseta al ancho de las rodillas. Y tiene que ser el camino
 * entero, no sus dos extremos: con las piernas dobladas, la recta entre la
 * cintura y el tobillo pasa por fuera del cuerpo.
 */
export function caminoDeLaPrenda(cuerpo: Cuerpo, categoria: GarmentCategory): Punto[] {
  return caminoDelCuerpo(cuerpo, categoria)
}

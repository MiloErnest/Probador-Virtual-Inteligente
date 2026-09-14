/**
 * Medir el cuerpo de la persona a partir de lo que devuelve MediaPipe.
 *
 * POR QUE ESTE MODULO EXISTE
 * --------------------------
 * La version anterior colocaba la prenda con un solo numero: "dibujala 1,9
 * veces mas ancha que la distancia entre hombros". Ese numero habia que
 * ajustarlo a mano por cada foto y por cada persona, y aun asi el largo salia
 * de la proporcion de la fotografia y no del cuerpo: una foto alta convertia
 * una camiseta en un vestido.
 *
 * Aqui se mide el cuerpo de verdad, y la prenda se coloca sobre esas medidas.
 *
 * LOS PUNTOS DE MEDIAPIPE NO SON EL BORDE DEL CUERPO
 * ---------------------------------------------------
 * Es la trampa principal, y la causa de aquel 1,9. Los puntos 11 y 12 estan
 * en la ARTICULACION del hombro, dentro del cuerpo, no en el borde exterior
 * del deltoides. Lo mismo con las caderas, que caen sobre el femur y no sobre
 * el contorno. Usar esa distancia como ancho del cuerpo deja la prenda
 * sistematicamente estrecha, y compensarlo con un multiplicador inventado es
 * lo que obligaba a tocar el control cada vez.
 *
 * Los factores de abajo son la correccion anatomica entre una medida y otra.
 * Siguen siendo aproximaciones, pero son las MISMAS para todo el mundo, que es
 * justo lo que un numero ajustado a ojo no puede prometer.
 */

import type { Landmark, NormalizedLandmark } from '@mediapipe/tasks-vision'

import { factorDeSuavizado } from '@/probador/inercia'

/** Indices de los puntos que usamos, de los 33 que devuelve el modelo. */
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

/** Por debajo de esto, el punto es una conjetura del modelo y no se usa. */
export const VISIBILIDAD_MINIMA = 0.5

/**
 * De la distancia entre articulaciones al ancho real del cuerpo.
 *
 * La anchura biacromial —de deltoides a deltoides— es alrededor de un tercio
 * mayor que la distancia entre los centros de las articulaciones del hombro.
 * En las caderas la diferencia es algo mayor, porque los puntos caen mas
 * adentro todavia.
 */
const HOMBROS_A_ANCHO_REAL = 1.34
const CADERAS_A_ANCHO_REAL = 1.42

export interface Punto {
  x: number
  y: number
}

export interface Cuerpo {
  hombroIzq: Punto
  hombroDer: Punto
  /** Punto medio de la linea de hombros. */
  hombros: Punto
  caderaIzq: Punto
  caderaDer: Punto
  caderas: Punto
  /** Null si la persona esta cortada por abajo, que con un portatil es lo normal. */
  rodillas: Punto | null
  tobillos: Punto | null

  /** Vector unitario que baja por el eje del torso, de hombros a caderas. */
  eje: Punto
  /** Angulo de ese eje. Es lo que gira la prenda cuando te inclinas. */
  inclinacion: number
  /** Distancia hombros-caderas en pixeles. Es la unidad de medida del cuerpo. */
  torso: number

  /** Ancho exterior del cuerpo, ya corregido, en pixeles. */
  anchoHombros: number
  anchoCaderas: number
}

function aPantalla(p: NormalizedLandmark, ancho: number, alto: number): Punto {
  return { x: p.x * ancho, y: p.y * alto }
}

function visible(p: NormalizedLandmark | undefined): boolean {
  return p !== undefined && (p.visibility ?? 1) >= VISIBILIDAD_MINIMA
}

function medio(a: Punto, b: Punto): Punto {
  return { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 }
}

/** Punto medio de dos landmarks, o null si alguno no se ve con confianza. */
function medioSiSeVe(
  landmarks: NormalizedLandmark[],
  a: number,
  b: number,
  ancho: number,
  alto: number,
): Punto | null {
  const pa = landmarks[a]
  const pb = landmarks[b]
  if (!visible(pa) || !visible(pb)) return null
  return medio(aPantalla(pa, ancho, alto), aPantalla(pb, ancho, alto))
}

/**
 * Convierte los puntos normalizados en medidas de pantalla.
 *
 * Devuelve null si no se ven los cuatro puntos imprescindibles (dos hombros y
 * dos caderas): sin ellos no se puede colocar nada con criterio, y es
 * preferible no dibujar a dibujar mal.
 */
export function medirCuerpo(
  landmarks: NormalizedLandmark[],
  ancho: number,
  alto: number,
): Cuerpo | null {
  const imprescindibles = [
    PUNTO.HOMBRO_IZQ,
    PUNTO.HOMBRO_DER,
    PUNTO.CADERA_IZQ,
    PUNTO.CADERA_DER,
  ]
  for (const i of imprescindibles) {
    if (!visible(landmarks[i])) return null
  }

  const hombroIzq = aPantalla(landmarks[PUNTO.HOMBRO_IZQ], ancho, alto)
  const hombroDer = aPantalla(landmarks[PUNTO.HOMBRO_DER], ancho, alto)
  const caderaIzq = aPantalla(landmarks[PUNTO.CADERA_IZQ], ancho, alto)
  const caderaDer = aPantalla(landmarks[PUNTO.CADERA_DER], ancho, alto)

  const hombros = medio(hombroIzq, hombroDer)
  const caderas = medio(caderaIzq, caderaDer)

  const dx = caderas.x - hombros.x
  const dy = caderas.y - hombros.y
  const torso = Math.hypot(dx, dy)

  // Sin un torso creible no hay escala de referencia. Pasa con alguien muy
  // girado o asomandose por el borde del encuadre.
  if (torso < 1) return null

  return {
    hombroIzq,
    hombroDer,
    hombros,
    caderaIzq,
    caderaDer,
    caderas,
    rodillas: medioSiSeVe(landmarks, PUNTO.RODILLA_IZQ, PUNTO.RODILLA_DER, ancho, alto),
    tobillos: medioSiSeVe(landmarks, PUNTO.TOBILLO_IZQ, PUNTO.TOBILLO_DER, ancho, alto),

    eje: { x: dx / torso, y: dy / torso },
    inclinacion: Math.atan2(dy, dx) - Math.PI / 2,
    torso,

    anchoHombros:
      Math.hypot(hombroDer.x - hombroIzq.x, hombroDer.y - hombroIzq.y) * HOMBROS_A_ANCHO_REAL,
    anchoCaderas:
      Math.hypot(caderaDer.x - caderaIzq.x, caderaDer.y - caderaIzq.y) * CADERAS_A_ANCHO_REAL,
  }
}

/**
 * Constante de tiempo del suavizado del cuerpo, en segundos.
 *
 * Son los segundos que tarda en recorrer el 63% de la distancia que le falta.
 * 0,04 s quita el temblor sin que se note el retraso al moverse.
 *
 * OJO: esto suaviza el CUERPO, que es la verdad de referencia. El retraso con
 * el que la prenda le sigue es otra cosa y vive en `inercia.ts`. Mezclarlas
 * seria confundir «medir bien» con «moverse como una tela».
 */
export const TAU_CUERPO = 0.04

/**
 * Mezcla la medida nueva con la anterior.
 *
 * POR QUE HACE FALTA
 * ------------------
 * El modelo reestima la pose en cada fotograma por separado, asi que los
 * puntos bailan uno o dos pixeles aunque la persona este quieta. Sin suavizar,
 * la prenda vibra sin parar y parece pegada con cinta.
 *
 * POR QUE RECIBE `dt` Y NO UN FACTOR
 * ----------------------------------
 * Antes era `factor = 0.35` aplicado en cada fotograma, y eso ata el
 * comportamiento a la tasa de refresco: a 120 Hz suaviza el doble de rapido
 * que a 60, y en un portatil que baja a 30 Hz cuando se calienta la prenda
 * cambia de caracter sola. Con el tiempo real transcurrido, el resultado es el
 * mismo en cualquier equipo.
 */
export function suavizarCuerpo(anterior: Cuerpo | null, actual: Cuerpo, dt: number): Cuerpo {
  if (anterior === null) return actual

  const factor = factorDeSuavizado(dt, TAU_CUERPO)

  // Un salto grande no es ruido: o la persona se ha movido de verdad, o el
  // modelo ha cambiado de persona. Suavizarlo dejaria la prenda arrastrandose
  // por la pantalla, asi que ahi se acepta la medida nueva tal cual.
  const salto = Math.hypot(
    actual.hombros.x - anterior.hombros.x,
    actual.hombros.y - anterior.hombros.y,
  )
  if (salto > actual.torso * 0.5) return actual

  const p = (a: Punto, b: Punto): Punto => ({
    x: a.x + (b.x - a.x) * factor,
    y: a.y + (b.y - a.y) * factor,
  })
  const pn = (a: Punto | null, b: Punto | null): Punto | null =>
    a === null || b === null ? b : p(a, b)
  const n = (a: number, b: number) => a + (b - a) * factor

  const hombros = p(anterior.hombros, actual.hombros)
  const caderas = p(anterior.caderas, actual.caderas)
  const dx = caderas.x - hombros.x
  const dy = caderas.y - hombros.y
  const torso = Math.max(1, Math.hypot(dx, dy))

  return {
    hombroIzq: p(anterior.hombroIzq, actual.hombroIzq),
    hombroDer: p(anterior.hombroDer, actual.hombroDer),
    hombros,
    caderaIzq: p(anterior.caderaIzq, actual.caderaIzq),
    caderaDer: p(anterior.caderaDer, actual.caderaDer),
    caderas,
    rodillas: pn(anterior.rodillas, actual.rodillas),
    tobillos: pn(anterior.tobillos, actual.tobillos),
    eje: { x: dx / torso, y: dy / torso },
    inclinacion: Math.atan2(dy, dx) - Math.PI / 2,
    torso,
    anchoHombros: n(anterior.anchoHombros, actual.anchoHombros),
    anchoCaderas: n(anterior.anchoCaderas, actual.anchoCaderas),
  }
}

// --- Caminos sobre el cuerpo -------------------------------------------------
//
// Una prenda no recorre una linea recta: un pantalon dobla por la rodilla y una
// persona inclinada no es un segmento vertical. El recorrido se describe con
// una polilinea de tres o cuatro puntos, y estas dos funciones son las que
// permiten repartir cualquier cosa a lo largo de ella.

/** Largo total de una polilinea. */
export function largoDelCamino(camino: Punto[]): number {
  let total = 0
  for (let i = 1; i < camino.length; i++) {
    total += Math.hypot(camino[i].x - camino[i - 1].x, camino[i].y - camino[i - 1].y)
  }
  return total
}

/** Punto y direccion a una distancia dada del comienzo de la polilinea. */
export function puntoEnCamino(camino: Punto[], distancia: number): { punto: Punto; direccion: Punto } {
  let recorrido = 0

  for (let i = 1; i < camino.length; i++) {
    const dx = camino[i].x - camino[i - 1].x
    const dy = camino[i].y - camino[i - 1].y
    const tramo = Math.hypot(dx, dy)

    if (recorrido + tramo >= distancia || i === camino.length - 1) {
      const t = tramo === 0 ? 0 : (distancia - recorrido) / tramo
      return {
        punto: { x: camino[i - 1].x + dx * t, y: camino[i - 1].y + dy * t },
        direccion: tramo === 0 ? { x: 0, y: 1 } : { x: dx / tramo, y: dy / tramo },
      }
    }
    recorrido += tramo
  }

  return { punto: camino[camino.length - 1], direccion: { x: 0, y: 1 } }
}

// --- Orientacion del torso -------------------------------------------------

/**
 * Hacia donde estas mirando, respecto a la camara.
 *
 * DE DONDE SALE
 * -------------
 * MediaPipe devuelve, ademas de los puntos en pantalla, unos `worldLandmarks`
 * que son coordenadas 3D en metros. Con la linea de hombros en el plano
 * horizontal ya se sabe si estas de frente o de perfil: de frente los dos
 * hombros estan a la misma distancia de la camara; girado, uno se acerca.
 *
 * POR QUE IMPORTA, SI EL ANCHO YA SE ENCOGE SOLO
 * ----------------------------------------------
 * El ancho si: los puntos de pantalla ya vienen proyectados, asi que al
 * girarte la distancia entre hombros se acorta sola y la prenda se estrecha.
 * Eso ya funcionaba.
 *
 * Lo que NO funcionaba es todo lo demas. La fotografia es del FRENTE de la
 * prenda, y se dibujaba igual de frente que de perfil: el estampado, los
 * botones y el cuello se quedaban mirando a la camara como un cartel pegado,
 * mientras el cuerpo giraba debajo. Con el giro medido se puede hacer que la
 * tela ruede alrededor del cuerpo, y desvanecerla cuando ya no queda frente
 * que enseñar — que es lo honesto, porque de la espalda no tenemos foto.
 */
export interface Orientacion {
  /** 1 = de frente a la camara. 0 = de perfil. */
  frontalidad: number
  /**
   * Hacia que lado has girado, de -1 a 1. 0 = de frente.
   *
   * Es el seno del angulo de giro, que es justo lo que hace falta: en un
   * cilindro, un punto del frente de la tela aparece desplazado `radio · giro`
   * al girar el cuerpo. De ahi sale el corrimiento de la textura.
   */
  giro: number
  /** La camara te esta viendo la espalda. */
  deEspaldas: boolean
}

export const ORIENTACION_FRONTAL: Orientacion = {
  frontalidad: 1,
  giro: 0,
  deEspaldas: false,
}

export function medirOrientacion(
  world: Landmark[],
  pantalla: NormalizedLandmark[],
): Orientacion {
  const wi = world[PUNTO.HOMBRO_IZQ]
  const wd = world[PUNTO.HOMBRO_DER]
  const pi = pantalla[PUNTO.HOMBRO_IZQ]
  const pd = pantalla[PUNTO.HOMBRO_DER]

  if (wi === undefined || wd === undefined || pi === undefined || pd === undefined) {
    return ORIENTACION_FRONTAL
  }

  const dx = wd.x - wi.x
  const dz = wd.z - wi.z
  const largo = Math.hypot(dx, dz)

  // Hombros pegados en el espacio: el modelo no esta seguro de nada. Mejor
  // suponer que estas de frente que inventarse un giro.
  if (!Number.isFinite(largo) || largo < 1e-4) return ORIENTACION_FRONTAL

  // `frontalidad` y `giro` son el coseno y el seno del angulo de giro, pero
  // calculados como cociente y no con atan2: asi no hay que preocuparse de en
  // que rama cae el angulo ni de que signo trae la z de MediaPipe.
  const frontalidad = Math.min(1, Math.abs(dx) / largo)
  const giro = Math.max(-1, Math.min(1, dz / largo))

  // DE ESPALDAS: el modelo mantiene la identidad izquierda/derecha del cuerpo
  // aunque te des la vuelta, asi que cuando lo hace, los dos hombros se cruzan
  // en pantalla. Ese cruce es la senal, y es barata y fiable.
  //
  // Se exige ademas estar bastante de frente: en pleno perfil los dos hombros
  // caen casi en la misma columna y el cruce se decide por medio pixel de
  // ruido, encendiendose y apagandose solo.
  const deEspaldas = frontalidad > 0.45 && pd.x - pi.x > 0

  return { frontalidad, giro, deEspaldas }
}

/** Constante de tiempo de la orientacion. Mas lenta que el cuerpo a
 *  proposito: la profundidad que estima el modelo es bastante mas ruidosa que
 *  la posicion en pantalla, y aqui un salto se ve como un parpadeo. */
export const TAU_ORIENTACION = 0.12

export function suavizarOrientacion(
  anterior: Orientacion | null,
  actual: Orientacion,
  dt: number,
): Orientacion {
  if (anterior === null) return actual
  const f = factorDeSuavizado(dt, TAU_ORIENTACION)
  return {
    frontalidad: anterior.frontalidad + (actual.frontalidad - anterior.frontalidad) * f,
    giro: anterior.giro + (actual.giro - anterior.giro) * f,
    // Un booleano no se interpola: se cambia cuando el modelo lo dice.
    deEspaldas: actual.deEspaldas,
  }
}

export interface Mascara {
  datos: Float32Array
  ancho: number
  alto: number
}

/** Devuelve el valor de la mascara en un punto del lienzo. 1 = persona. */
function esPersona(
  mascara: Mascara,
  lienzoAncho: number,
  lienzoAlto: number,
  x: number,
  y: number,
): number {
  const mx = Math.round((x / lienzoAncho) * mascara.ancho)
  const my = Math.round((y / lienzoAlto) * mascara.alto)
  if (mx < 0 || my < 0 || mx >= mascara.ancho || my >= mascara.alto) return 0
  return mascara.datos[my * mascara.ancho + mx]
}

/** Paso del barrido, en pixeles del lienzo. 2 basta y cuesta la mitad que 1. */
const PASO_BARRIDO = 2

/**
 * Mide el semiancho real de la persona a varias alturas.
 *
 * COMO
 * ----
 * Recorre el segmento `desde -> hasta` —el tramo del cuerpo que va a cubrir la
 * prenda— y en cada muestra se aleja del eje hacia los dos lados hasta salirse
 * de la silueta. Lo que devuelve es cuanto cuerpo hay a cada altura, medido
 * sobre la persona de verdad y no sobre una tabla de proporciones.
 *
 * POR QUE SE QUEDA CON EL PUNTO MAS LEJANO Y NO CON EL PRIMER HUECO
 * -----------------------------------------------------------------
 * Un pantalon tiene que cubrir las dos piernas, y entre ellas hay fondo. Si el
 * barrido se parara en el primer pixel que no es persona, a la altura de las
 * rodillas mediria cero, porque justo en el eje no hay nadie. Guardando la
 * distancia MAS LEJANA a la que todavia habia persona, las dos piernas quedan
 * dentro.
 *
 * Efecto secundario conocido: con los brazos separados del cuerpo, a la altura
 * del pecho el barrido los incluye y la prenda saldria ancha. Por eso quien
 * llama a esta funcion limita cuanto puede desviarse la medida del ancho
 * anatomico (ver `vestir.ts`): la mascara CORRIGE la silueta, no decide el
 * tamano.
 */
export function medirContorno(
  mascara: Mascara,
  lienzoAncho: number,
  lienzoAlto: number,
  camino: Punto[],
  muestras: number,
  radioMaximo: number,
): number[] {
  const largo = largoDelCamino(camino)
  if (largo < 1) return new Array<number>(muestras).fill(0)

  const semianchos: number[] = []

  for (let i = 0; i < muestras; i++) {
    const t = muestras === 1 ? 0 : i / (muestras - 1)

    // Se recorre el camino REAL, no la recta entre sus extremos. Con las
    // piernas dobladas, la recta pasa por fuera del cuerpo y mediria el aire.
    const { punto, direccion } = puntoEnCamino(camino, t * largo)
    const cx = punto.x
    const cy = punto.y
    // Perpendicular al cuerpo AHI: la direccion en la que se mide el ancho.
    const px = -direccion.y
    const py = direccion.x

    let izquierda = 0
    let derecha = 0

    for (let d = PASO_BARRIDO; d <= radioMaximo; d += PASO_BARRIDO) {
      if (esPersona(mascara, lienzoAncho, lienzoAlto, cx - px * d, cy - py * d) >= 0.5) {
        izquierda = d
      }
      if (esPersona(mascara, lienzoAncho, lienzoAlto, cx + px * d, cy + py * d) >= 0.5) {
        derecha = d
      }
    }

    // La prenda se dibuja centrada en el eje, asi que manda el lado mas ancho:
    // quedandose con el estrecho, el lado largo se saldria de la tela.
    semianchos.push(Math.max(izquierda, derecha))
  }

  return semianchos
}

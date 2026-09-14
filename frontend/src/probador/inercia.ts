/**
 * Inercia de la prenda: por que la ropa no te sigue al instante.
 *
 * EL PROBLEMA
 * -----------
 * Hasta ahora la prenda se colocaba exactamente donde estaba el cuerpo, en el
 * mismo fotograma. Y eso es justo lo que la delataba como pegatina: la ropa de
 * verdad tiene masa. Cuando te mueves, el bajo se queda atras; cuando paras,
 * se pasa de largo y vuelve. Ese medio segundo de retraso y rebote es casi
 * todo lo que separa «una tela puesta encima» de «una imagen pegada».
 *
 * COMO SE MODELA
 * --------------
 * Un muelle amortiguado que persigue al cuerpo. Dos parametros, y los dos
 * tienen significado fisico:
 *
 *   - FRECUENCIA (Hz): lo rapido que responde. Alta = se asienta enseguida.
 *   - AMORTIGUACION (zeta): cuanto rebota. 1 es el limite sin rebote; por
 *     debajo oscila, por encima va pastoso y lento.
 *
 * Se expresa asi, y no como dos constantes `k` y `c` sueltas, porque estas dos
 * se pueden razonar: «un cuero rebota poco y se para enseguida» son numeros
 * que se eligen solos. Con `k` y `c` habria que ir a tientas.
 *
 * POR QUE PASO FIJO Y NO EL DEL NAVEGADOR
 * ---------------------------------------
 * Es el error clasico al integrar un muelle, y no es cosmetico:
 *
 *   1. Con paso variable, el MISMO muelle oscila distinto a 60 Hz que a 30.
 *      La prenda cambiaria de comportamiento segun lo cargado que este el
 *      equipo, que es exactamente lo que no se quiere de una simulacion.
 *   2. Con un paso grande —cambias de pestana y vuelves 4 segundos despues—
 *      el metodo de Euler explota: la fuerza se aplica durante tanto tiempo
 *      que el muelle se pasa MAS lejos de lo que estaba, y en dos iteraciones
 *      se va al infinito. La prenda desaparece de la pantalla.
 *
 * La solucion estandar: se acumula el tiempo real y se consume en pasos fijos
 * de 1/120 s. El resultado no depende de la tasa de refresco. Y el numero de
 * pasos esta limitado, asi que una pausa larga no se recupera «simulando» los
 * cuatro segundos: se descarta y se coloca la prenda donde toca (ver
 * `SALTO_MAXIMO`).
 *
 * POR QUE EULER SEMI-IMPLICITO
 * ----------------------------
 * Se actualiza la velocidad primero y la posicion DESPUES, con la velocidad ya
 * nueva. Cuesta lo mismo que el Euler de toda la vida y es estable para
 * oscilaciones, mientras que el explicito le mete energia al sistema en cada
 * paso y acaba amplificando el rebote en lugar de apagarlo.
 */

export interface Muelle {
  /** Posicion actual, en pixeles del lienzo. */
  x: number
  y: number
  /** Velocidad, en pixeles por segundo. */
  vx: number
  vy: number
  /** Falso hasta el primer avance: sirve para colocarlo sin animacion. */
  activo: boolean
}

export function crearMuelle(): Muelle {
  return { x: 0, y: 0, vx: 0, vy: 0, activo: false }
}

/** Paso de integracion, en segundos. */
const PASO = 1 / 120

/**
 * Tiempo maximo que se simula de una vez.
 *
 * Por encima de esto no es una pausa entre fotogramas: es que la pestana ha
 * estado oculta, o el equipo se ha atascado. Simular ese tiempo no reproduce
 * nada real —el cuerpo tambien se movio mientras tanto y no lo sabemos—, asi
 * que se recoloca la prenda y se sigue.
 */
const SALTO_MAXIMO = 0.25

/**
 * Avanza el muelle hacia el objetivo.
 *
 * `dt` es el tiempo real transcurrido, en segundos. Mutar el objeto en vez de
 * devolver uno nuevo es deliberado: esto corre en el bucle de dibujo, y una
 * reserva de memoria por fotograma es basura que el recolector tiene que
 * barrer justo cuando peor viene.
 */
export function avanzarMuelle(
  muelle: Muelle,
  objetivoX: number,
  objetivoY: number,
  dt: number,
  frecuencia: number,
  amortiguacion: number,
): void {
  // Un objetivo invalido tira la transformacion del canvas al suelo sin decir
  // nada: un NaN en `translate` no lanza error, simplemente deja de dibujarse
  // todo lo que venga despues. Se corta aqui.
  if (!Number.isFinite(objetivoX) || !Number.isFinite(objetivoY)) return

  if (!muelle.activo || dt > SALTO_MAXIMO || !Number.isFinite(dt)) {
    colocarMuelle(muelle, objetivoX, objetivoY)
    return
  }

  // Rigidez y rozamiento, derivados de los dos parametros con sentido fisico.
  const w = 2 * Math.PI * frecuencia
  const k = w * w
  const c = 2 * amortiguacion * w

  let restante = dt
  while (restante > 0) {
    const h = restante < PASO ? restante : PASO

    // Semi-implicito: primero la velocidad, luego la posicion con la nueva.
    muelle.vx += ((objetivoX - muelle.x) * k - muelle.vx * c) * h
    muelle.vy += ((objetivoY - muelle.y) * k - muelle.vy * c) * h
    muelle.x += muelle.vx * h
    muelle.y += muelle.vy * h

    restante -= h
  }

  // Red de seguridad. Con parametros sensatos no salta nunca, pero si algun
  // dia alguien mete una frecuencia absurda es mejor recolocar la prenda que
  // verla salir disparada.
  if (!Number.isFinite(muelle.x) || !Number.isFinite(muelle.y)) {
    colocarMuelle(muelle, objetivoX, objetivoY)
  }
}

/** Deja el muelle quieto en un punto, sin animacion. */
export function colocarMuelle(muelle: Muelle, x: number, y: number): void {
  muelle.x = x
  muelle.y = y
  muelle.vx = 0
  muelle.vy = 0
  muelle.activo = true
}

/**
 * Mezcla exponencial que NO depende de la tasa de refresco.
 *
 * POR QUE NO VALE UN FACTOR FIJO POR FOTOGRAMA
 * --------------------------------------------
 * Es el fallo que tenia el suavizado del cuerpo: `mezclar(a, b, 0.35)` en cada
 * fotograma suaviza el doble de rapido a 120 Hz que a 60. En un portatil que
 * baja a 30 Hz cuando se calienta, la prenda cambia de comportamiento sola y
 * no hay forma de entender por que.
 *
 * Con una constante de tiempo, el resultado es el mismo a cualquier tasa:
 * `tau` es los segundos que tarda en recorrer el 63% de la distancia que le
 * falta, y eso es un tiempo de verdad.
 */
export function factorDeSuavizado(dt: number, tau: number): number {
  if (!Number.isFinite(dt) || dt <= 0) return 1
  if (tau <= 0) return 1
  return 1 - Math.exp(-dt / tau)
}

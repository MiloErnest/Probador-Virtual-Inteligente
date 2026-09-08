/**
 * Maniqui 3D dirigido por la pose real de la persona.
 *
 * DE DONDE SALE EL 3D
 * -------------------
 * No hay reconstruccion ni nada que adivinar: MediaPipe devuelve, ademas de
 * los puntos en pantalla, unos `worldLandmarks` que son coordenadas 3D EN
 * METROS con origen en el centro de las caderas. O sea que la postura de la
 * persona ya viene medida en el espacio; aqui solo se construye un cuerpo
 * encima.
 *
 * QUE ES TUYO EN ESTE MANIQUI Y QUE NO
 * ------------------------------------
 * Tuyo: la POSTURA (de los worldLandmarks) y las PROPORCIONES —los contornos
 * salen de las medidas del perfil corporal de la Fase 3, y los largos de
 * hueso, de la propia deteccion—.
 *
 * No tuyo: la cara, el pelo y la piel. Eso es reconstruccion fotorrealista de
 * una persona, que es GPU y modelos de investigacion. El maniqui es
 * deliberadamente neutro en vez de fingir un parecido que no tiene.
 *
 * POR QUE PRIMITIVAS Y NO UNA MALLA RIGADA
 * ----------------------------------------
 * Una malla humanoide con esqueleto se ve mejor, pero es un archivo de varios
 * MB que hay que traer, y el codigo de skinning es bastante mas. Con capsulas
 * entre articulaciones se llega a algo legible, sin ningun recurso externo, y
 * la postura se ve igual de bien. Si algun dia el aspecto importa mas que la
 * simplicidad, se sustituye esta clase entera sin tocar quien la usa.
 */

import * as THREE from 'three'

import type { BodyProfile } from '@/types'

/** Indices de MediaPipe. Los mismos que en overlay.ts, repetidos aqui para
 *  que este modulo no dependa del de dibujo 2D. */
const P = {
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
}

/** Huesos que se dibujan como capsula, con su grosor en metros. */
const HUESOS: { a: number; b: number; radio: number }[] = [
  { a: P.HOMBRO_IZQ, b: P.CODO_IZQ, radio: 0.045 },
  { a: P.CODO_IZQ, b: P.MUNECA_IZQ, radio: 0.035 },
  { a: P.HOMBRO_DER, b: P.CODO_DER, radio: 0.045 },
  { a: P.CODO_DER, b: P.MUNECA_DER, radio: 0.035 },
  { a: P.CADERA_IZQ, b: P.RODILLA_IZQ, radio: 0.065 },
  { a: P.RODILLA_IZQ, b: P.TOBILLO_IZQ, radio: 0.05 },
  { a: P.CADERA_DER, b: P.RODILLA_DER, radio: 0.065 },
  { a: P.RODILLA_DER, b: P.TOBILLO_DER, radio: 0.05 },
]

/** Contornos por defecto, en cm, cuando no hay perfil corporal guardado. */
const CONTORNO_POR_DEFECTO = { pecho: 94, cintura: 80, cadera: 98 }

/** Eje de referencia: las capsulas de Three nacen orientadas en Y. */
const EJE_Y = new THREE.Vector3(0, 1, 0)

/** Caja util de la prenda dentro de su imagen, en pixeles. */
export interface Caja {
  x: number
  y: number
  width: number
  height: number
}

interface Punto3D {
  x: number
  y: number
  z: number
  visibility?: number
}

export class Avatar3D {
  private readonly renderer: THREE.WebGLRenderer
  private readonly scene: THREE.Scene
  private readonly camera: THREE.PerspectiveCamera
  private readonly grupo = new THREE.Group()

  private readonly materialCuerpo: THREE.MeshStandardMaterial
  private readonly materialPrenda: THREE.MeshStandardMaterial

  private torso: THREE.Mesh | null = null
  private cabeza: THREE.Mesh | null = null
  private prenda: THREE.Mesh | null = null
  private readonly extremidades: THREE.Mesh[] = []

  private contornos = { ...CONTORNO_POR_DEFECTO }
  /** Angulo al que el usuario ha girado el maniqui, en radianes. */
  private giro = 0

  constructor(canvas: HTMLCanvasElement) {
    this.renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true })
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))

    this.scene = new THREE.Scene()
    this.camera = new THREE.PerspectiveCamera(35, 1, 0.1, 100)
    // A 2.6 m y un poco por encima del centro: encuadra a una persona entera
    // sin que la perspectiva le deforme la cabeza.
    this.camera.position.set(0, 0.1, 2.6)
    this.camera.lookAt(0, 0, 0)

    // Tres luces: una general para que nada quede negro, una principal que da
    // el volumen, y un relleno por detras que despega la silueta del fondo.
    this.scene.add(new THREE.AmbientLight(0xffffff, 1.1))
    const principal = new THREE.DirectionalLight(0xffffff, 1.6)
    principal.position.set(1.5, 2.5, 2)
    this.scene.add(principal)
    const relleno = new THREE.DirectionalLight(0x99bbff, 0.7)
    relleno.position.set(-2, 0.5, -1.5)
    this.scene.add(relleno)

    this.materialCuerpo = new THREE.MeshStandardMaterial({
      color: 0xc9b8a8,
      roughness: 0.85,
      metalness: 0,
    })
    this.materialPrenda = new THREE.MeshStandardMaterial({
      color: 0xffffff,
      roughness: 0.9,
      metalness: 0,
      // La prenda envuelve el torso: hay que ver su cara interior por detras.
      side: THREE.DoubleSide,
      transparent: true,
    })

    this.scene.add(this.grupo)
  }

  /** Ajusta el lienzo al tamano que le da el CSS. */
  resize(ancho: number, alto: number) {
    if (ancho === 0 || alto === 0) return
    this.renderer.setSize(ancho, alto, false)
    this.camera.aspect = ancho / alto
    this.camera.updateProjectionMatrix()
  }

  /** Gira el maniqui sobre su eje. Es lo que permite verse de lado y de espaldas. */
  girar(radianes: number) {
    this.giro = radianes
    this.grupo.rotation.y = radianes
  }

  get giroActual() {
    return this.giro
  }

  /**
   * Toma los contornos del perfil corporal.
   *
   * Es lo que convierte el maniqui en TU maniqui y no en uno generico: los
   * largos de hueso salen de la deteccion, pero el grosor del torso solo
   * puede venir de una medida real.
   */
  setMedidas(perfil: BodyProfile | null) {
    this.contornos = {
      pecho: perfil?.chest_cm ?? CONTORNO_POR_DEFECTO.pecho,
      cintura: perfil?.waist_cm ?? CONTORNO_POR_DEFECTO.cintura,
      cadera: perfil?.hips_cm ?? CONTORNO_POR_DEFECTO.cadera,
    }
  }

  /**
   * Envuelve el torso con la prenda.
   *
   * POR QUE NO SE USA LA IMAGEN TAL CUAL
   * ------------------------------------
   * Dos cosas salieron mal al intentarlo directo, y se vieron al mirarlo:
   *
   * 1. La foto recortada conserva los margenes transparentes del packshot. Al
   *    envolverla en el cilindro, la prenda util ocupaba una franja estrecha y
   *    el resto era aire. Por eso se recorta a su caja util antes de nada.
   *
   * 2. En la geometria de cilindro de Three, la coordenada u=0 cae en el
   *    FRENTE (+Z). Con la imagen ocupando toda la vuelta, la prenda aparecia
   *    a un lado o directamente por la espalda. Ahora la textura se construye
   *    con dos mitades —frente y espalda reflejada— y se desplaza para que el
   *    frente de la prenda quede mirando a la camara.
   *
   * La espalda es la misma imagen reflejada. No es la espalda real de la
   * prenda, que nadie fotografia en un packshot, pero es mucho mejor que
   * dejar el torso desnudo al girar.
   */
  setPrenda(recorte: HTMLCanvasElement | null, caja?: Caja) {
    this.materialPrenda.map?.dispose()

    if (recorte === null) {
      this.materialPrenda.map = null
      this.materialPrenda.visible = false
      this.materialPrenda.needsUpdate = true
      return
    }

    const util = caja ?? { x: 0, y: 0, width: recorte.width, height: recorte.height }

    // Lienzo del doble de ancho: mitad izquierda el frente, mitad derecha la
    // espalda. Asi la vuelta completa del cilindro queda cubierta.
    const lienzo = document.createElement('canvas')
    lienzo.width = util.width * 2
    lienzo.height = util.height
    const ctx = lienzo.getContext('2d')
    if (ctx === null) return

    // Frente, en la mitad izquierda.
    ctx.drawImage(recorte, util.x, util.y, util.width, util.height, 0, 0, util.width, util.height)

    // Espalda: la misma imagen reflejada, en la mitad derecha.
    ctx.save()
    ctx.translate(util.width * 2, 0)
    ctx.scale(-1, 1)
    ctx.drawImage(recorte, util.x, util.y, util.width, util.height, 0, 0, util.width, util.height)
    ctx.restore()

    const textura = new THREE.CanvasTexture(lienzo)
    textura.colorSpace = THREE.SRGBColorSpace
    // `RepeatWrapping` es imprescindible para que el desplazamiento de abajo
    // envuelva en vez de estirar el ultimo pixel.
    textura.wrapS = THREE.RepeatWrapping
    // El centro del frente esta en u=0.25 de la textura; u=0 de la geometria
    // mira a la camara. Desplazando 0.25 se hacen coincidir.
    textura.offset.x = 0.25

    this.materialPrenda.map = textura
    this.materialPrenda.visible = true
    this.materialPrenda.needsUpdate = true
  }

  /**
   * Reconstruye el cuerpo para la pose recibida.
   *
   * Se rehace la geometria en cada actualizacion en vez de deformar una malla
   * existente. Es mas caro, pero con ~11 primitivas es irrelevante, y evita
   * toda la complejidad de un esqueleto con pesos. Si algun dia se nota, el
   * sitio donde optimizar esta acotado a este metodo.
   */
  update(worldLandmarks: Punto3D[]): boolean {
    const necesarios = [P.HOMBRO_IZQ, P.HOMBRO_DER, P.CADERA_IZQ, P.CADERA_DER]
    for (const i of necesarios) {
      if (worldLandmarks[i] === undefined) return false
    }

    this.limpiar()

    const v = (i: number) => {
      const p = worldLandmarks[i]
      // MediaPipe usa Y hacia ABAJO; Three.js, hacia arriba. Sin este cambio
      // de signo el maniqui sale boca abajo, que es el primer sintoma cuando
      // algo va mal aqui.
      return new THREE.Vector3(p.x, -p.y, p.z)
    }

    const hombroIzq = v(P.HOMBRO_IZQ)
    const hombroDer = v(P.HOMBRO_DER)
    const caderaIzq = v(P.CADERA_IZQ)
    const caderaDer = v(P.CADERA_DER)

    const centroHombros = hombroIzq.clone().add(hombroDer).multiplyScalar(0.5)
    const centroCaderas = caderaIzq.clone().add(caderaDer).multiplyScalar(0.5)
    const largoTorso = centroHombros.distanceTo(centroCaderas)

    // Contorno -> radio. Un contorno es un perimetro, y la seccion del torso
    // se aproxima con un circulo: radio = perimetro / 2*PI.
    const radioPecho = this.contornos.pecho / 100 / (2 * Math.PI)
    const radioCadera = this.contornos.cadera / 100 / (2 * Math.PI)

    // Torso: cono truncado de cadera a pecho, para que se note la forma.
    const torsoGeom = new THREE.CylinderGeometry(radioPecho, radioCadera, largoTorso, 24, 1, true)
    this.torso = new THREE.Mesh(torsoGeom, this.materialCuerpo)
    this.colocarEntre(this.torso, centroCaderas, centroHombros)
    this.grupo.add(this.torso)

    // Cabeza: no hay landmark de coronilla fiable, asi que se coloca sobre los
    // hombros a una fraccion del torso. Es una aproximacion asumida.
    const anchoHombros = hombroIzq.distanceTo(hombroDer)
    const radioCabeza = Math.max(0.075, anchoHombros * 0.28)
    this.cabeza = new THREE.Mesh(
      new THREE.SphereGeometry(radioCabeza, 24, 16),
      this.materialCuerpo,
    )
    const direccionArriba = centroHombros.clone().sub(centroCaderas).normalize()
    this.cabeza.position.copy(
      centroHombros.clone().add(direccionArriba.multiplyScalar(radioCabeza * 1.5)),
    )
    this.grupo.add(this.cabeza)

    // Brazos y piernas.
    for (const hueso of HUESOS) {
      const a = worldLandmarks[hueso.a]
      const b = worldLandmarks[hueso.b]
      if (a === undefined || b === undefined) continue
      // Un punto poco visible es una conjetura del modelo. Dibujar un brazo
      // sobre una conjetura da posturas rotas muy llamativas.
      if ((a.visibility ?? 1) < 0.4 || (b.visibility ?? 1) < 0.4) continue

      const pa = v(hueso.a)
      const pb = v(hueso.b)
      const largo = pa.distanceTo(pb)
      if (largo < 0.02) continue

      const malla = new THREE.Mesh(
        new THREE.CapsuleGeometry(hueso.radio, largo, 6, 12),
        this.materialCuerpo,
      )
      this.colocarEntre(malla, pa, pb)
      this.extremidades.push(malla)
      this.grupo.add(malla)
    }

    // Prenda: cascara ligeramente mayor que el torso, con la foto plana
    // envuelta alrededor. Asi las fotos de producto sirven en 3D sin tener
    // que modelar nada.
    if (this.materialPrenda.map !== null) {
      const holgura = 1.12
      const prendaGeom = new THREE.CylinderGeometry(
        radioPecho * holgura,
        radioCadera * holgura,
        largoTorso * 1.05,
        28,
        1,
        true,
      )
      this.prenda = new THREE.Mesh(prendaGeom, this.materialPrenda)
      this.colocarEntre(this.prenda, centroCaderas, centroHombros)
      this.grupo.add(this.prenda)
    }

    // Centrar la figura en el encuadre: el origen esta en las caderas, asi
    // que sin esto la persona aparece pegada al borde inferior.
    this.grupo.position.y = -centroCaderas.y * 0 - 0.1

    return true
  }

  render() {
    this.renderer.render(this.scene, this.camera)
  }

  dispose() {
    this.limpiar()
    this.materialCuerpo.dispose()
    this.materialPrenda.map?.dispose()
    this.materialPrenda.dispose()
    this.renderer.dispose()
  }

  // --- Interno ---

  /** Coloca una malla alargada de `desde` a `hasta`, orientandola. */
  private colocarEntre(malla: THREE.Mesh, desde: THREE.Vector3, hasta: THREE.Vector3) {
    malla.position.copy(desde).add(hasta).multiplyScalar(0.5)
    const direccion = hasta.clone().sub(desde).normalize()
    malla.quaternion.setFromUnitVectors(EJE_Y, direccion)
  }

  /**
   * Libera la geometria de la pose anterior.
   *
   * Three.js no libera la memoria de la GPU al quitar una malla de la escena:
   * hay que llamar a dispose() a mano. Sin esto, reconstruir el cuerpo 30
   * veces por segundo agota la memoria grafica en menos de un minuto.
   */
  private limpiar() {
    const mallas = [this.torso, this.cabeza, this.prenda, ...this.extremidades]
    for (const malla of mallas) {
      if (malla === null) continue
      this.grupo.remove(malla)
      malla.geometry.dispose()
    }
    this.torso = null
    this.cabeza = null
    this.prenda = null
    this.extremidades.length = 0
  }
}

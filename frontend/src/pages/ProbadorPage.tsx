/**
 * El probador: tu foto, con una prenda de tu taller puesta.
 *
 * NO ES UN FLUJO APARTE
 * ---------------------
 * La prenda sale del taller: una prueba de tela —y entonces se usa la imagen
 * que ya se generó, no una nueva— o una prenda subida tal cual. Subir una
 * prenda nueva desde aquí usa el mismo `POST /garment-uploads` del taller, con
 * su recorte, y queda en el taller para probarle telas después.
 *
 * Antes esta pantalla era una cámara en vivo con su propio catálogo de ropa.
 * Se retiró: lo que se pedía era ver a una persona real, en su postura, con la
 * prenda que ha elegido para su tela.
 *
 * LO QUE SE DICE ANTES DE SUBIR LA FOTO
 * -------------------------------------
 * Que la foto sale del servidor hacia Hugging Face, y que del resultado solo se
 * toma la prenda. Lo primero porque es una foto de una persona; lo segundo
 * porque es la garantía que hace útil el resultado.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import { EmptyBlock, ErrorBlock, LoadingBlock, Notice } from '@/components/StateBlocks'
import { useApi } from '@/hooks/useApi'
import {
  createTryOn,
  deletePersonPhoto,
  deleteTryOn,
  fetchFabrics,
  fetchGarmentUploads,
  fetchPersonPhotos,
  fetchTrials,
  fetchTryOns,
  uploadGarment,
  uploadPersonPhoto,
} from '@/services/endpoints'
import {
  CATEGORY_LABELS,
  type GarmentCategory,
  type GarmentUpload,
  type PersonPhoto,
  type Trial,
  type TryOn,
} from '@/types'

/** Cada cuánto se pregunta por una prueba en marcha. */
const SONDEO_MS = 2000
/** Por encima del corte del modelo en el backend (240 s) más el análisis. */
const CORTE_MS = 300_000

/** La prenda elegida: de una prueba de tela, o subida tal cual. */
type Eleccion = { tipo: 'prueba'; id: number } | { tipo: 'prenda'; id: number }

export default function ProbadorPage() {
  const [params] = useSearchParams()

  const fotosFetcher = useCallback((signal: AbortSignal) => fetchPersonPhotos(signal), [])
  const fotos = useApi(fotosFetcher)
  const prendasFetcher = useCallback((signal: AbortSignal) => fetchGarmentUploads(signal), [])
  const prendas = useApi(prendasFetcher)
  const pruebasTelaFetcher = useCallback((signal: AbortSignal) => fetchTrials({ signal }), [])
  const pruebasTela = useApi(pruebasTelaFetcher)
  const telasFetcher = useCallback((signal: AbortSignal) => fetchFabrics({ signal }), [])
  const telas = useApi(telasFetcher)
  const probadasFetcher = useCallback((signal: AbortSignal) => fetchTryOns(signal), [])
  const probadasIniciales = useApi(probadasFetcher)

  const [foto, setFoto] = useState<number | null>(null)
  const [eleccion, setEleccion] = useState<Eleccion | null>(() => {
    const prueba = Number(params.get('prueba'))
    const prenda = Number(params.get('prenda'))
    if (prueba) return { tipo: 'prueba', id: prueba }
    if (prenda) return { tipo: 'prenda', id: prenda }
    return null
  })
  const [categoria, setCategoria] = useState<GarmentCategory>('top')
  const [probadas, setProbadas] = useState<TryOn[]>([])
  const [fallo, setFallo] = useState<string | null>(null)
  const [lanzando, setLanzando] = useState(false)

  useEffect(() => {
    if (probadasIniciales.data) setProbadas(probadasIniciales.data)
  }, [probadasIniciales.data])

  // La foto más reciente, elegida de entrada: casi siempre es la que se quiere.
  useEffect(() => {
    if (foto === null && fotos.data && fotos.data.length > 0) setFoto(fotos.data[0].id)
  }, [fotos.data, foto])

  const prendaPorId = useMemo(
    () => new Map((prendas.data ?? []).map((p) => [p.id, p] as const)),
    [prendas.data],
  )
  const nombreDeTela = useMemo(
    () => new Map((telas.data ?? []).map((t) => [t.id, t.name] as const)),
    [telas.data],
  )
  const conTela = useMemo(
    () => (pruebasTela.data ?? []).filter((p) => p.status === 'completed' && p.output_image_url),
    [pruebasTela.data],
  )

  // Al elegir prenda se propone la categoría por su nombre. Es solo una
  // propuesta: se ve y se cambia con un toque.
  useEffect(() => {
    if (!eleccion) return
    const subida =
      eleccion.tipo === 'prenda'
        ? prendaPorId.get(eleccion.id)
        : prendaPorId.get(conTela.find((p) => p.id === eleccion.id)?.garment_upload_id ?? -1)
    if (subida) setCategoria(adivinarCategoria(subida.name))
  }, [eleccion, prendaPorId, conTela])

  const enMarcha = probadas.some((p) => p.status === 'pending' || p.status === 'processing')

  useEffect(() => {
    if (!enMarcha) return
    const empezado = Date.now()
    const controlador = new AbortController()
    let activo = true
    const temporizador = window.setInterval(async () => {
      if (Date.now() - empezado > CORTE_MS) {
        window.clearInterval(temporizador)
        if (activo) setFallo('La prueba está tardando demasiado. Recarga la página en un rato.')
        return
      }
      try {
        const frescas = await fetchTryOns(controlador.signal)
        if (activo) setProbadas(frescas)
      } catch {
        // Un corte puntual de red no debe abortar el sondeo.
      }
    }, SONDEO_MS)
    return () => {
      activo = false
      controlador.abort()
      window.clearInterval(temporizador)
    }
  }, [enMarcha])

  async function probar() {
    if (foto === null || eleccion === null) return
    setFallo(null)
    setLanzando(true)
    try {
      const nueva = await createTryOn({
        personPhotoId: foto,
        category: categoria,
        ...(eleccion.tipo === 'prueba'
          ? { fabricTrialId: eleccion.id }
          : { garmentUploadId: eleccion.id }),
      })
      setProbadas((actuales) => [nueva, ...actuales])
    } catch (causa) {
      setFallo(causa instanceof Error ? causa.message : 'No se pudo lanzar la prueba.')
    } finally {
      setLanzando(false)
    }
  }

  /**
   * La misma foto con la misma prenda, otra vez. El servidor usa otra semilla
   * para cada prueba, así que sale otra variante: sirve cuando el modelo se ha
   * inventado algo —un cordón, un collar— que no está en la prenda.
   */
  async function otraVariante(probada: TryOn) {
    setFallo(null)
    try {
      const nueva = await createTryOn({
        personPhotoId: probada.person_photo_id,
        category: probada.category,
        ...(probada.fabric_trial_id !== null
          ? { fabricTrialId: probada.fabric_trial_id }
          : { garmentUploadId: probada.garment_upload_id ?? undefined }),
      })
      setProbadas((actuales) => [nueva, ...actuales])
      window.scrollTo({ top: 0, behavior: 'smooth' })
    } catch (causa) {
      setFallo(causa instanceof Error ? causa.message : 'No se pudo lanzar la prueba.')
    }
  }

  async function borrarProbada(id: number) {
    try {
      await deleteTryOn(id)
      setProbadas((actuales) => actuales.filter((p) => p.id !== id))
    } catch (causa) {
      setFallo(causa instanceof Error ? causa.message : 'No se pudo borrar.')
    }
  }

  async function borrarFoto(id: number) {
    try {
      await deletePersonPhoto(id)
      if (foto === id) setFoto(null)
      setProbadas((actuales) => actuales.filter((p) => p.person_photo_id !== id))
      fotos.reload()
    } catch (causa) {
      setFallo(causa instanceof Error ? causa.message : 'No se pudo borrar la foto.')
    }
  }

  const listo = foto !== null && eleccion !== null

  return (
    <div className="wrap space-y-12">
      <header>
        <p className="rotulo">Probador</p>
        <div className="mt-4 border-b border-ink-10 pb-6">
          <h1 className="font-display text-titulo">Pruébatela</h1>
          <p className="mt-2 max-w-2xl text-sm leading-relaxed text-ink-60">
            Sube una foto tuya y elige una prenda de tu taller, con la tela que escogiste. La
            prenda es exactamente la de tu prueba de tela: no se vuelve a dibujar. Da igual
            la postura: de pie, sentada, de lado.
          </p>
        </div>
      </header>

      <Notice title="Qué pasa con tu foto">
        <p>
          Se guarda sin metadatos: ni la ubicación ni el teléfono. Para vestirte se envía a{' '}
          <strong className="font-medium">FASHN VTON</strong>, un modelo abierto que corre en
          Hugging Face.
        </p>
        <p>
          Del resultado solo se toma la prenda, y la piel que la prenda nueva destapa o tapa.
          Tu cara, tu pelo, el resto de tu ropa y el fondo son los de tu foto original, píxel a
          píxel. Es gratis, con un número limitado de pruebas al día, y tarda alrededor de
          medio minuto.
        </p>
      </Notice>

      {fallo && <ErrorBlock title="Algo ha fallado" detail={fallo} />}

      <section className="space-y-4">
        <h2 className="rotulo">1 · Tu foto</h2>
        <ElegirFoto
          fotos={fotos.data}
          cargando={fotos.loading}
          error={fotos.error}
          elegida={foto}
          onElegir={setFoto}
          onBorrar={borrarFoto}
          onSubida={(nueva) => {
            setFoto(nueva.id)
            fotos.reload()
          }}
          onFallo={setFallo}
        />
      </section>

      <section className="space-y-4">
        <h2 className="rotulo">2 · La prenda</h2>
        <ElegirPrenda
          conTela={conTela}
          prendas={prendas.data}
          cargando={prendas.loading || pruebasTela.loading}
          nombreDeTela={nombreDeTela}
          prendaPorId={prendaPorId}
          elegida={eleccion}
          onElegir={setEleccion}
          onSubida={(nueva) => {
            setEleccion({ tipo: 'prenda', id: nueva.id })
            prendas.reload()
          }}
          onFallo={setFallo}
        />
      </section>

      <section className="space-y-4">
        <h2 className="rotulo">3 · Qué parte del cuerpo cubre</h2>
        <div role="radiogroup" className="flex flex-wrap gap-2">
          {(Object.keys(CATEGORY_LABELS) as GarmentCategory[]).map((valor) => (
            <button
              key={valor}
              type="button"
              role="radio"
              aria-checked={categoria === valor}
              onClick={() => setCategoria(valor)}
              className={`rounded-full border px-4 py-1.5 text-sm transition ${
                categoria === valor
                  ? 'border-ink bg-ink text-paper'
                  : 'border-ink-20 text-ink-60 hover:border-ink hover:text-ink'
              }`}
            >
              {CATEGORY_LABELS[valor]}
            </button>
          ))}
        </div>
        <p className="text-xs text-ink-60">
          Decide qué ropa de tu foto se cambia: una camisa no toca el pantalón; un vestido
          sustituye las dos.
        </p>
      </section>

      <div className="flex flex-wrap items-center gap-4 border-t border-ink-10 pt-6">
        <button type="button" className="btn-primary" disabled={!listo || lanzando} onClick={probar}>
          {lanzando ? 'Enviando…' : 'Probármela'}
        </button>
        {!listo && (
          <p className="text-sm text-ink-60">
            {foto === null ? 'Falta tu foto.' : 'Falta elegir la prenda.'}
          </p>
        )}
      </div>

      <section className="space-y-4">
        <div className="flex items-baseline justify-between gap-4">
          <h2 className="rotulo">Tus pruebas</h2>
          {enMarcha && <span className="text-xs text-ink-60">Vistiendo… (alrededor de medio minuto)</span>}
        </div>
        {probadasIniciales.loading ? (
          <LoadingBlock label="Cargando tus pruebas…" />
        ) : probadas.length === 0 ? (
          <EmptyBlock
            title="Todavía no te has probado nada"
            detail="Elige tu foto y una prenda arriba. El resultado aparece aquí, junto a tu foto original."
          />
        ) : (
          <ul className="space-y-8">
            {probadas.map((probada) => (
              <ResultadoDePrueba
                key={probada.id}
                probada={probada}
                onBorrar={borrarProbada}
                onOtraVariante={otraVariante}
              />
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}

/** Propone la categoría por el nombre de la prenda. Solo una propuesta. */
function adivinarCategoria(nombre: string): GarmentCategory {
  const texto = nombre.toLowerCase()
  if (/vestido|mono\b|enterizo|jumpsuit|dress/.test(texto)) return 'full'
  if (/pantal|falda|vaquero|jean|short|bermuda|skirt/.test(texto)) return 'bottom'
  return 'top'
}

function ElegirFoto({
  fotos,
  cargando,
  error,
  elegida,
  onElegir,
  onBorrar,
  onSubida,
  onFallo,
}: {
  fotos: PersonPhoto[] | null
  cargando: boolean
  error: string | null
  elegida: number | null
  onElegir: (id: number) => void
  onBorrar: (id: number) => void
  onSubida: (foto: PersonPhoto) => void
  onFallo: (mensaje: string) => void
}) {
  const entrada = useRef<HTMLInputElement | null>(null)
  const [subiendo, setSubiendo] = useState(false)

  async function subir(archivo: File | undefined) {
    if (!archivo) return
    setSubiendo(true)
    try {
      onSubida(await uploadPersonPhoto(archivo))
    } catch (causa) {
      onFallo(causa instanceof Error ? causa.message : 'No se pudo subir la foto.')
    } finally {
      setSubiendo(false)
      if (entrada.current) entrada.current.value = ''
    }
  }

  if (cargando && !fotos) return <LoadingBlock label="Cargando tus fotos…" />
  if (error) return <ErrorBlock title="No se pudieron cargar tus fotos" detail={error} />

  return (
    <div className="space-y-3">
      <ul className="grid grid-cols-3 gap-3 sm:grid-cols-5 lg:grid-cols-7">
        <li>
          <button
            type="button"
            onClick={() => entrada.current?.click()}
            disabled={subiendo}
            className="flex aspect-[3/4] w-full flex-col items-center justify-center gap-1 rounded border border-dashed border-ink-20 text-center text-xs text-ink-60 transition hover:border-ink hover:text-ink disabled:opacity-50"
          >
            <span className="text-2xl leading-none">+</span>
            {subiendo ? 'Subiendo…' : 'Subir una foto'}
          </button>
          <input
            ref={entrada}
            type="file"
            accept="image/jpeg,image/png,image/webp"
            className="hidden"
            onChange={(e) => subir(e.target.files?.[0])}
          />
        </li>
        {(fotos ?? []).map((f) => (
          <li key={f.id} className="space-y-1">
            <button
              type="button"
              aria-pressed={elegida === f.id}
              onClick={() => onElegir(f.id)}
              className={`block aspect-[3/4] w-full overflow-hidden rounded border-2 transition ${
                elegida === f.id ? 'border-ink' : 'border-transparent hover:border-ink-20'
              }`}
            >
              {f.image_url && (
                <img src={f.image_url} alt="Tu foto" className="h-full w-full object-cover" />
              )}
            </button>
            <div className="flex items-center justify-between px-0.5 text-[11px]">
              <span className={elegida === f.id ? 'font-medium' : 'text-ink-60'}>
                {elegida === f.id ? 'Elegida' : ' '}
              </span>
              <button
                type="button"
                onClick={() => onBorrar(f.id)}
                className="text-ink-60 underline underline-offset-4 hover:text-ink"
              >
                Borrar
              </button>
            </div>
          </li>
        ))}
      </ul>
      <p className="text-xs leading-relaxed text-ink-60">
        De cuerpo entero o de medio cuerpo, con la ropa que te quieras cambiar a la vista.
        Borrar una foto borra también las pruebas hechas con ella.
      </p>
    </div>
  )
}

function ElegirPrenda({
  conTela,
  prendas,
  cargando,
  nombreDeTela,
  prendaPorId,
  elegida,
  onElegir,
  onSubida,
  onFallo,
}: {
  conTela: Trial[]
  prendas: GarmentUpload[] | null
  cargando: boolean
  nombreDeTela: Map<number, string>
  prendaPorId: Map<number, GarmentUpload>
  elegida: Eleccion | null
  onElegir: (e: Eleccion) => void
  onSubida: (prenda: GarmentUpload) => void
  onFallo: (mensaje: string) => void
}) {
  const [pestana, setPestana] = useState<'tela' | 'tal-cual'>(
    elegida?.tipo === 'prenda' ? 'tal-cual' : 'tela',
  )
  const entrada = useRef<HTMLInputElement | null>(null)
  const [subiendo, setSubiendo] = useState(false)

  async function subir(archivo: File | undefined) {
    if (!archivo) return
    setSubiendo(true)
    try {
      // El mismo alta que en el taller: se recorta y se queda allí para
      // probarle telas después.
      const nombre = archivo.name.replace(/\.[a-z0-9]+$/i, '')
      onSubida(await uploadGarment(nombre, 'photo', archivo))
      setPestana('tal-cual')
    } catch (causa) {
      onFallo(causa instanceof Error ? causa.message : 'No se pudo subir la prenda.')
    } finally {
      setSubiendo(false)
      if (entrada.current) entrada.current.value = ''
    }
  }

  if (cargando && !prendas) return <LoadingBlock label="Cargando tu taller…" />

  const esta = (e: Eleccion) => elegida?.tipo === e.tipo && elegida.id === e.id

  return (
    <div className="space-y-4">
      <div role="tablist" className="inline-flex rounded border border-ink p-0.5">
        {(
          [
            ['tela', `Con tela (${conTela.length})`],
            ['tal-cual', `Tal cual (${prendas?.length ?? 0})`],
          ] as const
        ).map(([valor, texto]) => (
          <button
            key={valor}
            type="button"
            role="tab"
            aria-selected={pestana === valor}
            onClick={() => setPestana(valor)}
            className={`rounded-sm px-3 py-1.5 text-xs font-medium transition ${
              pestana === valor ? 'bg-ink text-paper' : 'text-ink-60 hover:text-ink'
            }`}
          >
            {texto}
          </button>
        ))}
      </div>

      {pestana === 'tela' ? (
        conTela.length === 0 ? (
          <EmptyBlock
            title="Aún no has probado telas"
            detail="Prueba una tela sobre una prenda en tu taller y aparecerá aquí, tal como salió."
            action={
              <Link to="/taller" className="btn-ghost">
                Ir a mi taller
              </Link>
            }
          />
        ) : (
          <ul className="grid grid-cols-3 gap-3 sm:grid-cols-5 lg:grid-cols-7">
            {conTela.map((p) => (
              <Miniatura
                key={p.id}
                imagen={p.output_image_url}
                titulo={nombreDeTela.get(p.fabric_id) ?? `Tela ${p.fabric_id}`}
                detalle={prendaPorId.get(p.garment_upload_id)?.name}
                elegida={esta({ tipo: 'prueba', id: p.id })}
                onElegir={() => onElegir({ tipo: 'prueba', id: p.id })}
              />
            ))}
          </ul>
        )
      ) : (
        <ul className="grid grid-cols-3 gap-3 sm:grid-cols-5 lg:grid-cols-7">
          <li>
            <button
              type="button"
              onClick={() => entrada.current?.click()}
              disabled={subiendo}
              className="flex aspect-[3/4] w-full flex-col items-center justify-center gap-1 rounded border border-dashed border-ink-20 px-2 text-center text-xs text-ink-60 transition hover:border-ink hover:text-ink disabled:opacity-50"
            >
              <span className="text-2xl leading-none">+</span>
              {subiendo ? 'Subiendo y recortando…' : 'Subir una prenda'}
            </button>
            <input
              ref={entrada}
              type="file"
              accept="image/jpeg,image/png,image/webp"
              className="hidden"
              onChange={(e) => subir(e.target.files?.[0])}
            />
          </li>
          {(prendas ?? []).map((p) => (
            <Miniatura
              key={p.id}
              imagen={p.image_url}
              titulo={p.name}
              detalle={p.kind === 'sketch' ? 'Boceto' : undefined}
              elegida={esta({ tipo: 'prenda', id: p.id })}
              onElegir={() => onElegir({ tipo: 'prenda', id: p.id })}
            />
          ))}
        </ul>
      )}
    </div>
  )
}

function Miniatura({
  imagen,
  titulo,
  detalle,
  elegida,
  onElegir,
}: {
  imagen: string | null
  titulo: string
  detalle?: string
  elegida: boolean
  onElegir: () => void
}) {
  return (
    <li>
      <button
        type="button"
        aria-pressed={elegida}
        onClick={onElegir}
        title={detalle ? `${titulo} · ${detalle}` : titulo}
        className="group block w-full text-left"
      >
        <span
          className={`block aspect-[3/4] overflow-hidden rounded border-2 bg-bone transition ${
            elegida ? 'border-ink' : 'border-transparent group-hover:border-ink-20'
          }`}
        >
          {imagen && <img src={imagen} alt={titulo} loading="lazy" className="h-full w-full object-contain" />}
        </span>
        <span className={`mt-1 block truncate text-[11px] ${elegida ? 'font-medium' : 'text-ink-60'}`}>
          {elegida ? `✓ ${titulo}` : titulo}
        </span>
        {detalle && <span className="block truncate text-[10px] text-ink-40">{detalle}</span>}
      </button>
    </li>
  )
}

function ResultadoDePrueba({
  probada,
  onBorrar,
  onOtraVariante,
}: {
  probada: TryOn
  onBorrar: (id: number) => void
  onOtraVariante: (probada: TryOn) => void
}) {
  const enCurso = probada.status === 'pending' || probada.status === 'processing'
  // Si se borró la prueba de tela o la prenda de origen, ya no hay con qué repetir.
  const repetible =
    !enCurso && (probada.fabric_trial_id !== null || probada.garment_upload_id !== null)

  return (
    <li className="grid gap-4 border-b border-ink-10 pb-8 sm:grid-cols-[1fr_1fr_140px]">
      <figure className="space-y-2">
        <div className="aspect-[3/4] overflow-hidden rounded border border-ink-10 bg-bone">
          {probada.person_image_url && (
            <img src={probada.person_image_url} alt="Tu foto" className="h-full w-full object-contain" />
          )}
        </div>
        <figcaption className="text-xs text-ink-60">Tu foto</figcaption>
      </figure>

      <figure className="space-y-2">
        <div className="relative aspect-[3/4] overflow-hidden rounded border border-ink bg-bone">
          {probada.output_image_url && (
            <img src={probada.output_image_url} alt="Con la prenda puesta" className="h-full w-full object-contain" />
          )}
          {enCurso && (
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-paper/70 backdrop-blur-sm">
              <span className="h-4 w-4 animate-spin rounded-full border border-ink-20 border-t-ink" />
              <span className="text-xs text-ink-60">Vistiendo…</span>
            </div>
          )}
          {probada.status === 'failed' && (
            <div className="absolute inset-0 flex items-center p-5">
              <p className="break-words text-sm leading-relaxed text-ink-80">
                <strong className="block font-medium">No se ha podido.</strong>
                {probada.error_message ?? 'Error desconocido.'}
              </p>
            </div>
          )}
        </div>
        <figcaption className="text-xs font-medium">Con la prenda puesta</figcaption>
      </figure>

      <div className="space-y-3">
        <div className="aspect-[3/4] overflow-hidden rounded border border-ink-10 bg-white">
          {probada.garment_image_url && (
            <img src={probada.garment_image_url} alt="La prenda enviada" className="h-full w-full object-contain" />
          )}
        </div>
        <div className="space-y-1 text-[11px] text-ink-60">
          <p className="font-medium text-ink">La prenda, tal cual se envió</p>
          <p>{CATEGORY_LABELS[probada.category]}</p>
          {probada.duration_ms !== null && <p>{(probada.duration_ms / 1000).toFixed(0)} s</p>}
          {probada.edited_fraction !== null && (
            <p>Del modelo: {(probada.edited_fraction * 100).toFixed(0)}% de la foto. El resto es tu foto.</p>
          )}
        </div>
        {probada.notice && <p className="break-words text-[11px] leading-relaxed text-ink-80">{probada.notice}</p>}
        {repetible && (
          <p className="text-[11px] leading-relaxed text-ink-60">
            ¿Algo que no está en tu prenda? Pide otra variante: el modelo la vuelve a generar
            de otra forma. Gasta una prueba de tu cuota.
          </p>
        )}
        <div className="flex flex-wrap gap-3">
          {repetible && (
            <button
              type="button"
              onClick={() => onOtraVariante(probada)}
              className="text-[11px] text-ink underline underline-offset-4"
            >
              Otra variante
            </button>
          )}
          <button
            type="button"
            onClick={() => onBorrar(probada.id)}
            className="text-[11px] text-ink-60 underline underline-offset-4 hover:text-ink"
          >
            Quitar
          </button>
        </div>
      </div>
    </li>
  )
}

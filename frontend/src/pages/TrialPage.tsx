/**
 * Probar telas sobre una prenda, y compararlas.
 *
 * ES LA PANTALLA DEL PRODUCTO
 * ---------------------------
 * Las otras existen para llegar aquí. El Product Vision Board pide cinco
 * cosas, y cuatro ocurren en esta pantalla: elegir tela del catálogo, ver la
 * prenda con ella, comparar opciones lado a lado, y el historial de pruebas.
 *
 * POR QUÉ LA COMPARACIÓN ES UNA REJILLA Y NO UN CARRUSEL
 * ------------------------------------------------------
 * Porque comparar es ver a la vez. Un carrusel obliga a recordar la anterior,
 * y decidir entre cuatro telas de memoria es justo lo que esta herramienta
 * viene a evitar.
 *
 * EL SONDEO
 * ---------
 * Crear una prueba responde 202: el resultado no viene en esa respuesta. Se
 * pregunta cada segundo y medio hasta que esté. Con el motor determinista es
 * un solo sondeo; con el generativo son veinte.
 */

import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { EmptyBlock, ErrorBlock, LoadingBlock, Notice } from '@/components/StateBlocks'
import { useApi } from '@/hooks/useApi'
import {
  createTrial,
  deleteTrial,
  fetchFabrics,
  fetchGarmentUpload,
  fetchTrials,
} from '@/services/endpoints'
import {
  GARMENT_KIND_LABELS,
  TRIAL_METHOD_LABELS,
  type Fabric,
  type Trial,
  type TrialMethod,
} from '@/types'

/** Cada cuánto se pregunta por una prueba en marcha. */
const SONDEO_MS = 1500
/** Cuándo dejar de esperar. El motor generativo puede tardar medio minuto. */
const CORTE_MS = 120_000

export default function TrialPage() {
  const { id } = useParams()
  const prendaId = Number(id)

  const prendaFetcher = useCallback(
    (signal: AbortSignal) => fetchGarmentUpload(prendaId, signal),
    [prendaId],
  )
  const { data: prenda, loading, error } = useApi(prendaFetcher, [prendaId])

  // Se piden TODAS y se filtran aquí abajo. El retexturizado estampa el
  // mosaico de la tela y sin mosaico no puede hacer nada; la IA trabaja con la
  // descripción de la ficha, así que le sirve una tela que aún no esté
  // fotografiada. Filtrar en el servidor dejaría fuera telas que sí se pueden
  // probar por el otro camino.
  const telasFetcher = useCallback((signal: AbortSignal) => fetchFabrics({ signal }), [])
  const { data: telas } = useApi(telasFetcher)

  const pruebasFetcher = useCallback(
    (signal: AbortSignal) => fetchTrials({ garmentUploadId: prendaId, signal }),
    [prendaId],
  )
  const { data: pruebasIniciales } = useApi(pruebasFetcher, [prendaId])

  const [pruebas, setPruebas] = useState<Trial[]>([])
  const [fallo, setFallo] = useState<string | null>(null)
  const [lanzando, setLanzando] = useState<number | null>(null)

  // Arranca en el determinista, y no por preferencia: está medido. La IA
  // devuelve una prenda distinta de la que se le manda, y encima se cobra.
  // Quien la quiera, que la pida.
  const [motor, setMotor] = useState<TrialMethod>('retexture')

  useEffect(() => {
    if (pruebasIniciales) setPruebas(pruebasIniciales)
  }, [pruebasIniciales])

  const enMarcha = useMemo(
    () => pruebas.some((p) => p.status === 'pending' || p.status === 'processing'),
    [pruebas],
  )

  // Sondeo. Se relanza la lista entera y no prueba a prueba: son pocas, y una
  // sola petición mantiene la rejilla coherente en lugar de ir actualizándose
  // a trozos.
  useEffect(() => {
    if (!enMarcha) return

    const empezado = Date.now()
    const controlador = new AbortController()
    let activo = true

    const temporizador = window.setInterval(async () => {
      if (Date.now() - empezado > CORTE_MS) {
        window.clearInterval(temporizador)
        if (activo) setFallo('Alguna prueba está tardando demasiado. Recarga la página.')
        return
      }
      try {
        const frescas = await fetchTrials({
          garmentUploadId: prendaId,
          signal: controlador.signal,
        })
        if (activo) setPruebas(frescas)
      } catch {
        // Un corte puntual de red no debe abortar el sondeo.
      }
    }, SONDEO_MS)

    return () => {
      activo = false
      controlador.abort()
      window.clearInterval(temporizador)
    }
  }, [enMarcha, prendaId])

  async function probar(tela: Fabric) {
    setFallo(null)
    setLanzando(tela.id)
    try {
      const prueba = await createTrial({
        garmentUploadId: prendaId,
        fabricId: tela.id,
        method: motor,
      })
      setPruebas((actuales) => [prueba, ...actuales])
    } catch (causa) {
      setFallo(causa instanceof Error ? causa.message : 'No se pudo lanzar la prueba.')
    } finally {
      setLanzando(null)
    }
  }

  async function borrar(trialId: number) {
    try {
      await deleteTrial(trialId)
      setPruebas((actuales) => actuales.filter((p) => p.id !== trialId))
    } catch (causa) {
      setFallo(causa instanceof Error ? causa.message : 'No se pudo borrar.')
    }
  }

  const porId = useMemo(
    () => new Map((telas ?? []).map((t) => [t.id, t] as const)),
    [telas],
  )

  const telasVisibles = useMemo(
    () => (motor === 'retexture' ? (telas ?? []).filter((t) => t.texture_url) : (telas ?? [])),
    [telas, motor],
  )

  if (loading) return <LoadingBlock label="Cargando la prenda…" />

  if (error || !prenda) {
    return (
      <div className="wrap">
        <ErrorBlock
          title="No se pudo cargar la prenda"
          detail={error ?? 'No existe, o no es tuya.'}
          action={
            <Link to="/taller" className="btn-ghost">
              Volver al taller
            </Link>
          }
        />
      </div>
    )
  }

  return (
    <div className="wrap space-y-10">
      <header>
        <Link to="/taller" className="rotulo hover:text-ink">
          ← Mi taller
        </Link>
        <div className="mt-4 flex flex-wrap items-end justify-between gap-x-8 gap-y-3 border-b border-ink-10 pb-6">
          <div>
            <h1 className="font-display text-titulo">{prenda.name}</h1>
            <p className="mt-2 text-sm text-ink-60">
              {GARMENT_KIND_LABELS[prenda.kind]}
              {prenda.kind === 'sketch' && ' · se rellena conservando el trazo'}
            </p>
          </div>
          <p className="text-sm text-ink-60">
            {pruebas.length} {pruebas.length === 1 ? 'prueba' : 'pruebas'}
          </p>
        </div>
      </header>

      {fallo && <ErrorBlock title="Algo ha fallado" detail={fallo} />}

      {prenda.mask_warning && (
        <Notice title="El recorte de esta prenda no ha salido bien">
          <p>{prenda.mask_warning}</p>
        </Notice>
      )}

      <section className="space-y-4">
        <div className="flex flex-wrap items-end justify-between gap-x-8 gap-y-3">
          <h2 className="rotulo">Elige una tela</h2>
          <SelectorDeMotor valor={motor} onCambiar={setMotor} />
        </div>

        {motor === 'ai' && <AvisoDeIA />}

        {telas === null ? (
          <LoadingBlock label="Cargando telas…" />
        ) : telasVisibles.length === 0 ? (
          <EmptyBlock
            title="No hay telas que se puedan probar"
            detail={
              motor === 'retexture'
                ? 'El retexturizado estampa el mosaico de la tela, y ninguna lo tiene cargado. Súbelo desde el catálogo, o cambia a IA generativa.'
                : 'El catálogo de telas está vacío.'
            }
          />
        ) : (
          <ul className="grid grid-cols-3 gap-3 sm:grid-cols-5 lg:grid-cols-8">
            {telasVisibles.map((tela) => (
              <li key={tela.id}>
                <button
                  type="button"
                  onClick={() => probar(tela)}
                  disabled={lanzando !== null}
                  title={`${tela.name}${tela.composition ? ` · ${tela.composition}` : ''}`}
                  className="group block w-full text-left disabled:opacity-50"
                >
                  <span
                    className="block aspect-square overflow-hidden rounded border border-ink-10 transition group-hover:border-ink"
                    style={{ backgroundColor: tela.color_hex ?? '#f7f7f5' }}
                  >
                    {tela.texture_url && (
                      <img
                        src={tela.texture_url}
                        alt={tela.name}
                        loading="lazy"
                        className="h-full w-full object-cover"
                      />
                    )}
                  </span>
                  <span className="mt-1.5 block truncate text-[11px] leading-tight text-ink-60">
                    {lanzando === tela.id ? 'Lanzando…' : tela.name}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="space-y-4">
        <div className="flex items-baseline justify-between gap-4">
          <h2 className="rotulo">Comparar</h2>
          {enMarcha && <span className="text-xs text-ink-60">Generando…</span>}
        </div>

        {pruebas.length === 0 ? (
          <EmptyBlock
            title="Todavía no has probado ninguna tela"
            detail="Elige una arriba. La primera tarda menos de un segundo."
          />
        ) : (
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {/* La prenda original va la primera, como referencia. Comparar
                cuatro telas sin ver de qué se partía no dice nada. */}
            <figure className="space-y-2">
              <div className="aspect-[4/5] overflow-hidden rounded border border-ink bg-bone">
                {prenda.image_url && (
                  <img
                    src={prenda.image_url}
                    alt={prenda.name}
                    className="h-full w-full object-contain"
                  />
                )}
              </div>
              <figcaption className="text-xs font-medium">Original</figcaption>
            </figure>

            {pruebas.map((prueba) => (
              <ResultadoDePrueba
                key={prueba.id}
                prueba={prueba}
                tela={porId.get(prueba.fabric_id)}
                onBorrar={borrar}
              />
            ))}
          </div>
        )}
      </section>
    </div>
  )
}

function ResultadoDePrueba({
  prueba,
  tela,
  onBorrar,
}: {
  prueba: Trial
  tela: Fabric | undefined
  onBorrar: (id: number) => void
}) {
  const enCurso = prueba.status === 'pending' || prueba.status === 'processing'

  return (
    <figure className="space-y-2">
      <div className="relative aspect-[4/5] overflow-hidden rounded border border-ink-10 bg-bone">
        {prueba.output_image_url && (
          <img
            src={prueba.output_image_url}
            alt={tela?.name ?? 'Resultado'}
            className="h-full w-full object-contain"
          />
        )}

        {enCurso && (
          <div className="absolute inset-0 flex items-center justify-center bg-paper/70 backdrop-blur-sm">
            <span className="h-4 w-4 animate-spin rounded-full border border-ink-20 border-t-ink" />
          </div>
        )}

        {prueba.status === 'failed' && (
          <div className="absolute inset-0 flex items-center p-4">
            <p className="text-xs leading-relaxed text-ink-80">
              {prueba.error_message ?? 'No se pudo generar.'}
            </p>
          </div>
        )}
      </div>

      <figcaption className="space-y-1">
        <p className="truncate text-xs font-medium">{tela?.name ?? `Tela ${prueba.fabric_id}`}</p>
        <p className="flex flex-wrap gap-x-2 text-[11px] text-ink-60">
          <span>{TRIAL_METHOD_LABELS[prueba.method]}</span>
          {prueba.duration_ms !== null && <span>{prueba.duration_ms} ms</span>}
          {/* Los tokens solo aparecen cuando los hay: que el motor gratis no
              enseñe un «0 tokens» es intencionado, porque la diferencia entre
              gratis y barato es la que hay que ver de un vistazo. */}
          {prueba.tokens_used !== null && <span>{prueba.tokens_used} tokens</span>}
        </p>

        {tela?.price_per_meter != null && (
          <p className="text-[11px] text-ink-60">
            {tela.price_per_meter.toFixed(2)} {tela.currency}/m
            {tela.reference && ` · ${tela.reference}`}
          </p>
        )}

        {prueba.notice && (
          <p className="text-[11px] leading-relaxed text-ink-80">{prueba.notice}</p>
        )}

        <button
          type="button"
          onClick={() => onBorrar(prueba.id)}
          className="text-[11px] text-ink-60 underline underline-offset-4 hover:text-ink"
        >
          Quitar
        </button>
      </figcaption>
    </figure>
  )
}

/**
 * Con qué motor se prueba.
 *
 * NO SE DISTINGUE SOLO POR EL RELLENO
 * -----------------------------------
 * El botón elegido va en negro, pero debajo hay una frase que dice qué cuesta
 * el motor seleccionado. Quien no distinga el contraste lee la frase, y el
 * lector de pantalla oye el `aria-pressed`. Es la misma regla que sigue el
 * resto de la interfaz: los estados se dicen con palabras, no con color.
 */
function SelectorDeMotor({
  valor,
  onCambiar,
}: {
  valor: TrialMethod
  onCambiar: (motor: TrialMethod) => void
}) {
  return (
    <div className="flex flex-col gap-1.5 sm:items-end">
      <div
        role="group"
        aria-label="Motor de la prueba"
        className="inline-flex self-start rounded border border-ink p-0.5 sm:self-auto"
      >
        {(['retexture', 'ai'] as const).map((opcion) => (
          <button
            key={opcion}
            type="button"
            aria-pressed={valor === opcion}
            onClick={() => onCambiar(opcion)}
            className={`rounded-sm px-3 py-1.5 text-xs font-medium transition ${
              valor === opcion ? 'bg-ink text-paper' : 'text-ink-60 hover:text-ink'
            }`}
          >
            {TRIAL_METHOD_LABELS[opcion]}
          </button>
        ))}
      </div>
      <p className="text-[11px] text-ink-60">
        {valor === 'retexture'
          ? 'Instantáneo, gratis, y siempre el mismo resultado.'
          : 'Unos 45 s, y consume tokens de OpenAI.'}
      </p>
    </div>
  )
}

/**
 * Lo que va a pasar, dicho ANTES de que cueste dinero.
 *
 * No es un descargo de responsabilidad de relleno. Está medido contra la API
 * real, y lo que dice es incómodo: el motor generativo devuelve una prenda
 * parecida, no la tuya. Para una herramienta que promete «mira TU diseño con
 * otra tela», eso es justo el resultado equivocado — y se cobra. Quien lo pulse
 * tiene derecho a saberlo antes, no a descubrirlo en la factura.
 */
function AvisoDeIA() {
  return (
    <Notice title="La IA vuelve a dibujar la prenda; no le cambia la tela">
      <p>
        Probado contra la API real con un boceto de camisa que tenía cartera de
        botones, cinco botones, bolsillo de pecho y cuello camisero: volvió
        convertido en una túnica lisa. Las dos veces, también con la fidelidad
        alta y con el modelo grande.
      </p>
      <p>
        Sirve para ver un boceto <strong>como fotografía</strong>, que es algo
        que el otro motor no sabe hacer. Para comparar telas sobre tu diseño sin
        que el diseño cambie, usa el retexturizado.
      </p>
      <p>Tarda unos 45 s, gasta tokens de tu cuenta, y el tope son 20 pruebas cada 24 h.</p>
    </Notice>
  )
}

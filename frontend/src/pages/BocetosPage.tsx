/**
 * Bocetos: del dibujo a la prenda, con IA generativa.
 *
 * POR QUÉ ES UNA PANTALLA APARTE
 * ------------------------------
 * Porque es el único sitio del producto donde la IA inventa, y el único que
 * cuesta dinero. En el taller todo es exacto y gratis; mezclar las dos cosas
 * en el mismo formulario escondía la diferencia que más le importa a quien
 * paga.
 *
 * Un boceto no es una prenda: es el dibujo de una. Aquí la IA lo convierte en
 * la fotografía de esa prenda, UNA vez. Después la prenda va al taller y las
 * telas se le prueban como a cualquier otra, sin IA y sin coste.
 *
 * EL DIBUJO Y LA PRENDA, SIEMPRE LADO A LADO
 * ------------------------------------------
 * El modelo interpreta el dibujo; no se le puede obligar a calcarlo. Lo que sí
 * se puede es no dar por buena una prenda sin mirarla: por eso cada tarjeta
 * enseña las dos imágenes juntas, con el parecido de la silueta en número, y
 * ofrece otra variante.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { Link } from 'react-router-dom'

import { EmptyBlock, ErrorBlock, LoadingBlock, Notice } from '@/components/StateBlocks'
import { useApi } from '@/hooks/useApi'
import {
  createGarmentVariant,
  deleteGarmentUpload,
  fetchGarmentUploads,
  uploadGarment,
} from '@/services/endpoints'
import type { GarmentUpload } from '@/types'

/** Cada cuánto se pregunta por una prenda que se está generando. */
const SONDEO_MS = 2000
/** Cuándo dejar de esperar: el corte de la llamada al modelo son 100 s. */
const CORTE_MS = 150_000

const soloBocetos = (prendas: GarmentUpload[]) => prendas.filter((p) => p.kind === 'sketch')

export default function BocetosPage() {
  const fetcher = useCallback((signal: AbortSignal) => fetchGarmentUploads(signal), [])
  const { data, loading, error } = useApi(fetcher)

  const [bocetos, setBocetos] = useState<GarmentUpload[]>([])
  const [nombre, setNombre] = useState('')
  const [archivo, setArchivo] = useState<File | null>(null)
  const [subiendo, setSubiendo] = useState(false)
  const [pidiendo, setPidiendo] = useState<number | null>(null)
  const [fallo, setFallo] = useState<string | null>(null)
  const entradaRef = useRef<HTMLInputElement | null>(null)

  useEffect(() => {
    if (data) setBocetos(soloBocetos(data))
  }, [data])

  const enMarcha = useMemo(
    () => bocetos.some((b) => b.status === 'pending' || b.status === 'processing'),
    [bocetos],
  )

  // Sondeo, igual que en las pruebas de tela: se relanza la lista entera.
  useEffect(() => {
    if (!enMarcha) return

    const empezado = Date.now()
    const controlador = new AbortController()
    let activo = true

    const temporizador = window.setInterval(async () => {
      if (Date.now() - empezado > CORTE_MS) {
        window.clearInterval(temporizador)
        if (activo) setFallo('La prenda está tardando demasiado. Recarga la página.')
        return
      }
      try {
        const frescas = await fetchGarmentUploads(controlador.signal)
        if (activo) setBocetos(soloBocetos(frescas))
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

  async function subir(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    if (archivo === null) return

    setFallo(null)
    setSubiendo(true)
    try {
      const nuevo = await uploadGarment(nombre.trim() || archivo.name, 'sketch', archivo)
      setBocetos((actuales) => [nuevo, ...actuales])
      setNombre('')
      setArchivo(null)
      if (entradaRef.current) entradaRef.current.value = ''
    } catch (causa) {
      setFallo(causa instanceof Error ? causa.message : 'No se pudo subir el boceto.')
    } finally {
      setSubiendo(false)
    }
  }

  async function otraVariante(id: number) {
    setFallo(null)
    setPidiendo(id)
    try {
      const prenda = await createGarmentVariant(id)
      // Una prenda fallida se reintenta en su misma fila; si no, llega una nueva.
      setBocetos((actuales) =>
        actuales.some((b) => b.id === prenda.id)
          ? actuales.map((b) => (b.id === prenda.id ? prenda : b))
          : [prenda, ...actuales],
      )
    } catch (causa) {
      setFallo(causa instanceof Error ? causa.message : 'No se pudo pedir la variante.')
    } finally {
      setPidiendo(null)
    }
  }

  async function borrar(id: number) {
    try {
      await deleteGarmentUpload(id)
      setBocetos((actuales) => actuales.filter((b) => b.id !== id))
    } catch (causa) {
      setFallo(causa instanceof Error ? causa.message : 'No se pudo borrar.')
    }
  }

  return (
    <div className="wrap space-y-10">
      <header>
        <p className="rotulo">Bocetos · IA generativa</p>
        <div className="mt-4 border-b border-ink-10 pb-6">
          <h1 className="font-display text-titulo">De tu boceto a la prenda</h1>
          <p className="mt-2 max-w-xl text-sm leading-relaxed text-ink-60">
            Sube el dibujo de una prenda que todavía no existe. La IA la convierte en su
            fotografía, y sobre ella pruebas las telas del catálogo como con cualquier otra.
          </p>
        </div>
      </header>

      {fallo && <ErrorBlock title="Algo ha fallado" detail={fallo} />}

      <section className="grid gap-8 lg:grid-cols-[360px_minmax(0,1fr)] lg:gap-12">
        <div className="space-y-5">
          <form onSubmit={subir} className="space-y-5 rounded border border-ink-10 p-6">
            <h2 className="rotulo">Subir un boceto</h2>

            <div className="space-y-1.5">
              <label htmlFor="nombre" className="block text-sm font-medium">
                Nombre
              </label>
              <input
                id="nombre"
                type="text"
                maxLength={160}
                value={nombre}
                onChange={(e) => setNombre(e.target.value)}
                placeholder="Vestido de noche, modelo 2"
                className="campo"
              />
            </div>

            <div className="space-y-1.5">
              <label htmlFor="archivo" className="block text-sm font-medium">
                Dibujo
              </label>
              <input
                id="archivo"
                ref={entradaRef}
                type="file"
                accept="image/jpeg,image/png,image/webp"
                required
                onChange={(e) => setArchivo(e.target.files?.[0] ?? null)}
                className="block w-full text-sm text-ink-60 file:mr-3 file:rounded-full file:border file:border-ink-20 file:bg-paper file:px-4 file:py-1.5 file:text-sm file:text-ink hover:file:border-ink"
              />
              <p className="text-xs leading-relaxed text-ink-60">
                La prenda entera y de frente. Si el dibujo tiene color, se respeta; si es
                solo lápiz, la prenda sale en tela cruda, sin teñir.
              </p>
            </div>

            <button type="submit" className="btn-primary w-full" disabled={subiendo || !archivo}>
              {subiendo ? 'Subiendo…' : 'Generar la prenda'}
            </button>
          </form>

          <Notice title="Lo que hace la IA aquí, y lo que cuesta">
            <p>
              Interpreta tu dibujo: la prenda se parecerá a él, pero no es un calco. Por eso
              la ves siempre junto al boceto, y puedes pedir otra variante.
            </p>
            <p>
              Cada prenda generada tarda alrededor de un minuto y gasta tokens de OpenAI. El
              tope son 20 cada 24 h. Probarle telas después no gasta nada.
            </p>
          </Notice>
        </div>

        <div className="space-y-6">
          {loading && <LoadingBlock label="Cargando tus bocetos…" />}

          {error && !loading && <ErrorBlock title="No se pudieron cargar" detail={error} />}

          {!loading && !error && bocetos.length === 0 && (
            <EmptyBlock
              title="Todavía no has subido ningún boceto"
              detail="Sube un dibujo para ver la prenda que saldría de él."
            />
          )}

          {bocetos.length > 0 && (
            <ul className="grid gap-8 xl:grid-cols-2">
              {bocetos.map((boceto) => (
                <TarjetaDeBoceto
                  key={boceto.id}
                  boceto={boceto}
                  ocupado={pidiendo !== null}
                  onVariante={otraVariante}
                  onBorrar={borrar}
                />
              ))}
            </ul>
          )}
        </div>
      </section>
    </div>
  )
}

function TarjetaDeBoceto({
  boceto,
  ocupado,
  onVariante,
  onBorrar,
}: {
  boceto: GarmentUpload
  ocupado: boolean
  onVariante: (id: number) => void
  onBorrar: (id: number) => void
}) {
  const lista = boceto.status === 'ready'
  const enCurso = boceto.status === 'pending' || boceto.status === 'processing'
  const fallida = boceto.status === 'failed'

  return (
    <li className="space-y-3">
      {/* El dibujo y la prenda, a la misma altura: comparar es ver a la vez. */}
      <div className="grid grid-cols-2 gap-3">
        <figure className="space-y-2">
          <div className="aspect-[3/4] overflow-hidden rounded border border-ink-10 bg-bone">
            {boceto.sketch_url && (
              <img
                src={boceto.sketch_url}
                alt={`Boceto de ${boceto.name}`}
                loading="lazy"
                className="h-full w-full object-contain"
              />
            )}
          </div>
          <figcaption className="rotulo">Tu boceto</figcaption>
        </figure>

        <figure className="space-y-2">
          <div
            className={`relative aspect-[3/4] overflow-hidden rounded border bg-bone ${
              lista ? 'border-ink' : 'border-dashed border-ink-20'
            }`}
          >
            {lista && boceto.image_url && (
              <img
                src={boceto.image_url}
                alt={`Prenda generada de ${boceto.name}`}
                loading="lazy"
                className="h-full w-full object-contain"
              />
            )}

            {enCurso && (
              <div
                role="status"
                className="absolute inset-0 flex flex-col items-center justify-center gap-3 p-4 text-center"
              >
                <span
                  className="h-4 w-4 animate-spin rounded-full border border-ink-20 border-t-ink"
                  aria-hidden
                />
                <p className="text-xs leading-relaxed text-ink-60">
                  Generando la prenda…
                  <br />
                  Alrededor de un minuto.
                </p>
              </div>
            )}

            {fallida && (
              <div className="absolute inset-0 flex items-center p-4">
                <p className="text-xs leading-relaxed text-ink-80">
                  {boceto.error_message ?? 'No se pudo generar la prenda.'}
                </p>
              </div>
            )}
          </div>
          <figcaption className="rotulo">
            {lista ? 'La prenda' : fallida ? 'Sin prenda' : 'Generando'}
          </figcaption>
        </figure>
      </div>

      <div className="space-y-2 px-1">
        <h3 className="truncate text-sm font-medium">{boceto.name}</h3>

        {lista && boceto.similarity !== null && (
          <p className="flex flex-wrap gap-x-2 text-[11px] text-ink-60">
            <span>Silueta: {Math.round(boceto.similarity * 100)} % de coincidencia con el boceto</span>
            {boceto.tokens_used !== null && <span>{boceto.tokens_used} tokens</span>}
          </p>
        )}

        <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
          {lista && (
            <>
              <Link
                to={`/taller/${boceto.id}`}
                className="text-xs font-medium text-ink underline underline-offset-4"
              >
                Probar telas
              </Link>
              <Link
                to={`/probador?prenda=${boceto.id}`}
                className="text-xs text-ink underline underline-offset-4"
              >
                Probármela
              </Link>
            </>
          )}
          {(lista || fallida) && (
            <button
              type="button"
              onClick={() => onVariante(boceto.id)}
              disabled={ocupado}
              title="Vuelve a pedirle la prenda a la IA. Gasta tokens."
              className="text-xs text-ink underline underline-offset-4 disabled:opacity-50"
            >
              {fallida ? 'Generar la prenda' : 'Otra variante'}
            </button>
          )}
          <button
            type="button"
            onClick={() => onBorrar(boceto.id)}
            className="text-xs text-ink-60 underline underline-offset-4 hover:text-ink"
          >
            Borrar
          </button>
        </div>

        {lista && boceto.similarity_warning && (
          <Notice title="La prenda se aparta de tu dibujo">
            <p className="text-xs">{boceto.similarity_warning}</p>
          </Notice>
        )}

        {lista && boceto.mask_warning && (
          <Notice title="El recorte no ha salido bien">
            <p className="text-xs">{boceto.mask_warning}</p>
          </Notice>
        )}
      </div>
    </li>
  )
}

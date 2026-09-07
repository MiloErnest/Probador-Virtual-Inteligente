/**
 * Perfil corporal y talla (Fase 3).
 *
 * Dos formas de rellenar las medidas: escribirlas a mano, o estimarlas desde
 * una foto. Las manuales tienen prioridad conceptual —son mas fiables— y la
 * pantalla lo dice cuando las medidas vienen de un analisis.
 *
 * El analisis es SINCRONO: tarda ~1 s y no hace falta sondear, a diferencia
 * del probador y del generador de disenos.
 */

import { useCallback, useState } from 'react'
import type { FormEvent } from 'react'

import { ErrorBlock, LoadingBlock } from '@/components/StateBlocks'
import { useApi } from '@/hooks/useApi'
import { ApiError } from '@/services/apiClient'
import {
  analyseBodyPhoto,
  deleteBodyProfile,
  fetchBodyProfile,
  fetchSizeRecommendation,
  saveBodyProfile,
} from '@/services/endpoints'
import type { BodyMeasurements, BodyProfile, GarmentCategory, SizeRecommendation } from '@/types'
import { CATEGORY_LABELS, MEASUREMENT_LABELS, MEASUREMENT_UNITS } from '@/types'

const CAMPOS: (keyof BodyMeasurements)[] = [
  'height_cm',
  'weight_kg',
  'chest_cm',
  'waist_cm',
  'hips_cm',
  'inseam_cm',
]

const CATEGORIAS: GarmentCategory[] = ['top', 'bottom', 'dress', 'outerwear']

export default function BodyProfilePage() {
  const fetcher = useCallback(
    async (signal: AbortSignal) => {
      try {
        return await fetchBodyProfile(signal)
      } catch (causa) {
        // 404 no es un error aqui: significa "todavia no tienes perfil", que
        // es el estado inicial normal de cualquier usuario nuevo.
        if (causa instanceof ApiError && causa.status === 404) return null
        throw causa
      }
    },
    [],
  )
  const { data: perfil, loading, error, reload } = useApi<BodyProfile | null>(fetcher)

  const [borrador, setBorrador] = useState<Record<string, string>>({})
  const [guardando, setGuardando] = useState(false)
  const [mensaje, setMensaje] = useState<string | null>(null)
  const [fallo, setFallo] = useState<string | null>(null)

  const [foto, setFoto] = useState<File | null>(null)
  const [analizando, setAnalizando] = useState(false)

  const [talla, setTalla] = useState<SizeRecommendation | null>(null)
  const [categoria, setCategoria] = useState<GarmentCategory>('top')

  function valorDe(campo: keyof BodyMeasurements): string {
    if (campo in borrador) return borrador[campo]
    const guardado = perfil?.[campo]
    return guardado === null || guardado === undefined ? '' : String(guardado)
  }

  async function guardar(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setFallo(null)
    setMensaje(null)

    // Solo se envia lo que el usuario ha tocado: la API hace actualizacion
    // parcial y no queremos reenviar valores que no han cambiado.
    const cambios: BodyMeasurements = {}
    for (const [campo, texto] of Object.entries(borrador)) {
      if (texto.trim() === '') continue
      const numero = Number(texto)
      if (Number.isNaN(numero)) {
        setFallo(`${MEASUREMENT_LABELS[campo]} no es un numero valido.`)
        return
      }
      cambios[campo as keyof BodyMeasurements] = numero
    }

    if (Object.keys(cambios).length === 0) {
      setFallo('No has cambiado ninguna medida.')
      return
    }

    setGuardando(true)
    try {
      await saveBodyProfile(cambios)
      setBorrador({})
      setMensaje('Medidas guardadas.')
      reload()
    } catch (causa) {
      setFallo(causa instanceof Error ? causa.message : 'No se pudieron guardar.')
    } finally {
      setGuardando(false)
    }
  }

  async function analizar() {
    if (foto === null) return
    setFallo(null)
    setMensaje(null)
    setAnalizando(true)
    try {
      const alturaTexto = valorDe('height_cm')
      const altura = alturaTexto === '' ? undefined : Number(alturaTexto)
      await analyseBodyPhoto(foto, altura)
      setFoto(null)
      setBorrador({})
      setMensaje('Medidas estimadas a partir de la fotografia.')
      reload()
    } catch (causa) {
      setFallo(causa instanceof Error ? causa.message : 'No se pudo analizar la foto.')
    } finally {
      setAnalizando(false)
    }
  }

  async function calcularTalla(cat: GarmentCategory) {
    setCategoria(cat)
    setFallo(null)
    try {
      setTalla(await fetchSizeRecommendation({ category: cat }))
    } catch (causa) {
      setTalla(null)
      setFallo(causa instanceof Error ? causa.message : 'No se pudo calcular la talla.')
    }
  }

  async function borrar() {
    setFallo(null)
    try {
      await deleteBodyProfile()
      setTalla(null)
      setBorrador({})
      setMensaje('Perfil corporal eliminado.')
      reload()
    } catch (causa) {
      setFallo(causa instanceof Error ? causa.message : 'No se pudo borrar.')
    }
  }

  return (
    <div className="max-w-3xl space-y-8">
      <header>
        <h1 className="font-display text-3xl">Perfil corporal</h1>
        <p className="mt-1.5 text-sm text-ink-muted">
          Tus medidas sirven para recomendarte talla. Solo las ves tu.
        </p>
      </header>

      {fallo && <ErrorBlock title="Algo ha fallado" detail={fallo} />}
      {mensaje && (
        <div className="card border-green-200 bg-green-50/60 px-5 py-3 text-sm text-green-900">
          {mensaje}
        </div>
      )}

      {loading && <LoadingBlock label="Cargando tu perfil…" />}
      {error && !loading && <ErrorBlock title="No se pudo cargar el perfil" detail={error} />}

      {!loading && !error && (
        <>
          {perfil?.source === 'analysis' && (
            <div className="card border-amber-200 bg-amber-50/60 px-5 py-4 text-sm text-amber-900">
              <strong className="font-medium">Estas medidas son estimaciones.</strong> Salen de
              una fotografia, no de una cinta metrica. Corrigelas a mano si conoces las reales:
              la recomendacion de talla mejorara bastante.
            </div>
          )}

          <section className="space-y-4">
            <h2 className="font-display text-xl">Tus medidas</h2>
            <form onSubmit={guardar} className="card space-y-4 p-6">
              <div className="grid gap-4 sm:grid-cols-2">
                {CAMPOS.map((campo) => (
                  <div key={campo} className="space-y-1.5">
                    <label htmlFor={campo} className="block text-sm font-medium">
                      {MEASUREMENT_LABELS[campo]}{' '}
                      <span className="text-ink-muted">({MEASUREMENT_UNITS[campo]})</span>
                    </label>
                    <input
                      id={campo}
                      type="number"
                      step="0.1"
                      value={valorDe(campo)}
                      onChange={(e) =>
                        setBorrador((previo) => ({ ...previo, [campo]: e.target.value }))
                      }
                      className="w-full rounded-lg border border-black/10 bg-white px-3.5 py-2.5 text-sm"
                    />
                  </div>
                ))}
              </div>
              <p className="text-xs text-ink-muted">
                No hace falta rellenarlas todas. Con el pecho ya se puede tallar una camisa;
                con cintura y cadera, un pantalon.
              </p>
              <div className="flex flex-wrap gap-3">
                <button type="submit" className="btn-primary" disabled={guardando}>
                  {guardando ? 'Guardando…' : 'Guardar medidas'}
                </button>
                {perfil && (
                  <button type="button" className="btn-ghost" onClick={borrar}>
                    Borrar mi perfil
                  </button>
                )}
              </div>
            </form>
          </section>

          <section className="space-y-3">
            <h2 className="font-display text-xl">O estimalas desde una foto</h2>
            <div className="card space-y-4 p-6">
              <div className="rounded-lg bg-amber-50/60 px-4 py-3 text-sm text-amber-900">
                <strong className="font-medium">Analisis simulado.</strong> Todavia no hay
                vision por computador: las medidas se derivan de proporciones medias sobre tu
                altura. Sirve para probar el flujo completo.
              </div>
              <p className="text-sm text-ink-muted">
                Foto vertical, de cuerpo entero y de frente. Indicar tu altura arriba mejora
                mucho el resultado, porque es la referencia que convierte proporciones en
                centimetros.
              </p>
              <input
                type="file"
                accept="image/jpeg,image/png,image/webp"
                onChange={(e) => setFoto(e.target.files?.[0] ?? null)}
                className="text-sm file:mr-3 file:rounded-full file:border-0 file:bg-ink file:px-4 file:py-2 file:text-sm file:text-white"
              />
              <button
                type="button"
                className="btn-ghost"
                onClick={analizar}
                disabled={foto === null || analizando}
              >
                {analizando ? 'Analizando…' : 'Estimar mis medidas'}
              </button>
            </div>
          </section>

          <section className="space-y-3">
            <h2 className="font-display text-xl">Que talla te corresponde</h2>
            <div className="flex flex-wrap gap-2">
              {CATEGORIAS.map((cat) => (
                <button
                  key={cat}
                  type="button"
                  onClick={() => calcularTalla(cat)}
                  className={`rounded-full border px-4 py-1.5 text-sm ${
                    categoria === cat && talla
                      ? 'border-ink bg-ink text-white'
                      : 'border-black/10 text-ink hover:bg-black/[0.04]'
                  }`}
                >
                  {CATEGORY_LABELS[cat]}
                </button>
              ))}
            </div>

            {talla && (
              <div className="card p-6">
                {talla.size ? (
                  <>
                    <p className="font-display text-4xl">{talla.size}</p>
                    <p className="mt-2 text-sm text-ink-soft">{talla.reason}</p>
                    {Object.keys(talla.per_measurement).length > 1 && (
                      <dl className="mt-4 flex flex-wrap gap-x-6 gap-y-1 text-xs text-ink-muted">
                        {Object.entries(talla.per_measurement).map(([medida, t]) => (
                          <div key={medida} className="flex gap-1.5">
                            <dt>{MEASUREMENT_LABELS[`${medida}_cm`] ?? medida}:</dt>
                            <dd className="font-medium">{t}</dd>
                          </div>
                        ))}
                      </dl>
                    )}
                    <p className="mt-4 text-xs text-ink-muted">
                      Fiabilidad: {Math.round(talla.confidence * 100)} %. Las tablas son
                      genericas; cada marca talla distinto.
                    </p>
                  </>
                ) : (
                  <p className="text-sm text-ink-soft">{talla.reason}</p>
                )}
              </div>
            )}
          </section>
        </>
      )}
    </div>
  )
}

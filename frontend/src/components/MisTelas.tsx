/**
 * Mis telas: las que el usuario fotografía en su taller (Ep6-Hu7 a Hu11).
 *
 * EL MOSAICO SE VE ANTES DE GUARDAR
 * ---------------------------------
 * De la foto sale el mosaico que se estampa sobre la prenda, y una foto mala
 * da un mosaico malo. Por eso «Guardar» no se activa hasta haber visto la
 * vista previa: el mosaico repetido 2 × 2, para que una costura se vea, su
 * junta medida y los avisos sobre la foto. Cambiar la foto o el tipo la anula.
 *
 * Nada de esto usa IA generativa: el mosaico lo calcula el motor, gratis.
 */

import { useCallback, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { Link } from 'react-router-dom'

import { EmptyBlock, ErrorBlock, LoadingBlock, Notice } from '@/components/StateBlocks'
import { useApi } from '@/hooks/useApi'
import {
  createMyFabric,
  deleteMyFabric,
  fetchMyFabrics,
  previewMyFabric,
  updateMyFabric,
} from '@/services/endpoints'
import {
  OWN_FABRIC_PATTERN_LABELS,
  type Fabric,
  type FabricPreview,
  type OwnFabricPattern,
} from '@/types'

const TIPOS = Object.keys(OWN_FABRIC_PATTERN_LABELS) as OwnFabricPattern[]

export default function MisTelas() {
  const fetcher = useCallback((signal: AbortSignal) => fetchMyFabrics({ signal }), [])
  const { data, loading, error, reload } = useApi(fetcher)

  const [nombre, setNombre] = useState('')
  const [tipo, setTipo] = useState<OwnFabricPattern>('solid')
  const [composicion, setComposicion] = useState('')
  const [repeticion, setRepeticion] = useState(6)
  const [archivo, setArchivo] = useState<File | null>(null)
  const [vista, setVista] = useState<FabricPreview | null>(null)
  const [ocupado, setOcupado] = useState<'vista' | 'guardar' | null>(null)
  const [fallo, setFallo] = useState<string | null>(null)
  const [hecho, setHecho] = useState<string | null>(null)
  const entradaRef = useRef<HTMLInputElement | null>(null)

  function anularVista() {
    setVista(null)
    setHecho(null)
  }

  async function verMosaico() {
    if (!archivo) return
    setFallo(null)
    setOcupado('vista')
    try {
      setVista(await previewMyFabric(tipo, archivo))
    } catch (causa) {
      setVista(null)
      setFallo(causa instanceof Error ? causa.message : 'No se pudo calcular el mosaico.')
    } finally {
      setOcupado(null)
    }
  }

  async function guardar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    if (!archivo || !vista) return
    setFallo(null)
    setOcupado('guardar')
    try {
      const creada = await createMyFabric({
        name: nombre.trim() || archivo.name.replace(/\.[^.]+$/, ''),
        pattern: tipo,
        file: archivo,
        composition: composicion.trim() || undefined,
        defaultRepeat: repeticion,
      })
      setHecho(`«${creada.name}» ya está entre tus telas. Elígela al probar una prenda.`)
      setNombre('')
      setComposicion('')
      setRepeticion(6)
      setArchivo(null)
      setVista(null)
      if (entradaRef.current) entradaRef.current.value = ''
      reload()
    } catch (causa) {
      setFallo(causa instanceof Error ? causa.message : 'No se pudo guardar la tela.')
    } finally {
      setOcupado(null)
    }
  }

  return (
    <section className="space-y-6" aria-labelledby="mis-telas">
      <div className="border-b border-ink-10 pb-6">
        <p className="rotulo">Tu taller</p>
        <h2 id="mis-telas" className="mt-2 scroll-mt-28 font-display text-2xl">
          Mis telas
        </h2>
        <p className="mt-2 max-w-xl text-sm leading-relaxed text-ink-60">
          Fotografía una tela que tengas en el taller y pruébala sobre tus prendas como
          cualquiera del catálogo. Solo la ves tú. Gratis: no usa IA generativa.
        </p>
      </div>

      {fallo && <ErrorBlock title="Algo ha fallado" detail={fallo} />}
      {hecho && (
        <Notice title="Tela guardada">
          <p>
            {hecho}{' '}
            <Link to="/taller" className="font-medium underline underline-offset-4">
              Ir a mi taller
            </Link>
          </p>
        </Notice>
      )}

      <div className="grid gap-8 lg:grid-cols-[380px_minmax(0,1fr)] lg:gap-12">
        <form onSubmit={guardar} className="space-y-5 rounded border border-ink-10 p-6">
          <h3 className="rotulo">Añadir una tela desde una foto</h3>

          <div className="space-y-1.5">
            <label htmlFor="tela-nombre" className="block text-sm font-medium">
              Nombre
            </label>
            <input
              id="tela-nombre"
              type="text"
              maxLength={160}
              value={nombre}
              onChange={(e) => setNombre(e.target.value)}
              placeholder="Paño granate del estante 2"
              className="campo"
            />
          </div>

          <fieldset className="space-y-2">
            <legend className="text-sm font-medium">¿Cómo es la tela?</legend>
            <div className="flex flex-wrap gap-2">
              {TIPOS.map((valor) => (
                <button
                  key={valor}
                  type="button"
                  aria-pressed={tipo === valor}
                  onClick={() => {
                    setTipo(valor)
                    anularVista()
                  }}
                  className={`rounded-full border px-4 py-1.5 text-sm transition ${
                    tipo === valor
                      ? 'border-ink bg-ink text-paper'
                      : 'border-ink-20 text-ink-60 hover:border-ink hover:text-ink'
                  }`}
                >
                  {OWN_FABRIC_PATTERN_LABELS[valor]}
                </button>
              ))}
            </div>
          </fieldset>

          <div className="space-y-1.5">
            <label htmlFor="tela-foto" className="block text-sm font-medium">
              Foto de la tela
            </label>
            <input
              id="tela-foto"
              ref={entradaRef}
              type="file"
              accept="image/jpeg,image/png,image/webp"
              required
              onChange={(e) => {
                setArchivo(e.target.files?.[0] ?? null)
                anularVista()
              }}
              className="block w-full text-sm text-ink-60 file:mr-3 file:rounded-full file:border file:border-ink-20 file:bg-paper file:px-4 file:py-1.5 file:text-sm file:text-ink hover:file:border-ink"
            />
            <p className="text-xs leading-relaxed text-ink-60">
              De frente, con la tela llenando el encuadre y luz de ventana sin sol directo.
              Se usa el centro de la foto.
            </p>
          </div>

          <div className="grid grid-cols-[minmax(0,1fr)_7rem] gap-3">
            <div className="space-y-1.5">
              <label htmlFor="tela-composicion" className="block text-sm font-medium">
                Composición <span className="font-normal text-ink-40">(opcional)</span>
              </label>
              <input
                id="tela-composicion"
                type="text"
                maxLength={160}
                value={composicion}
                onChange={(e) => setComposicion(e.target.value)}
                placeholder="100% algodón"
                className="campo"
              />
            </div>
            <div className="space-y-1.5">
              <label htmlFor="tela-repeticion" className="block text-sm font-medium">
                Repeticiones
              </label>
              <input
                id="tela-repeticion"
                type="number"
                min={1}
                max={40}
                value={repeticion}
                onChange={(e) => setRepeticion(Math.min(40, Math.max(1, Number(e.target.value) || 1)))}
                className="campo"
              />
            </div>
          </div>
          <p className="-mt-3 text-xs text-ink-60">
            Repeticiones: cuántas veces cabe el mosaico a lo ancho de la prenda. Más, el
            dibujo sale más pequeño.
          </p>

          <button
            type="button"
            className="btn-ghost w-full"
            disabled={!archivo || ocupado !== null}
            onClick={verMosaico}
          >
            {ocupado === 'vista' ? 'Calculando el mosaico…' : 'Ver el mosaico'}
          </button>

          {vista && <VistaPrevia vista={vista} />}

          <button
            type="submit"
            className="btn-primary w-full"
            disabled={!vista || ocupado !== null}
          >
            {ocupado === 'guardar' ? 'Guardando…' : 'Guardar tela'}
          </button>
          {!vista && archivo && (
            <p className="text-center text-xs text-ink-60">Mira el mosaico antes de guardarla.</p>
          )}
        </form>

        <div className="space-y-6">
          {loading && <LoadingBlock label="Cargando tus telas…" />}
          {error && !loading && <ErrorBlock title="No se pudieron cargar" detail={error} />}
          {!loading && !error && data?.length === 0 && (
            <EmptyBlock
              title="Todavía no has añadido ninguna tela"
              detail="Las que fotografíes aparecerán aquí y al elegir tela para una prenda."
            />
          )}
          {!loading && !error && data && data.length > 0 && (
            <ul className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3">
              {data.map((tela) => (
                <TarjetaDeTela key={tela.id} tela={tela} onCambio={reload} onFallo={setFallo} />
              ))}
            </ul>
          )}
        </div>
      </div>
    </section>
  )
}

function VistaPrevia({ vista }: { vista: FabricPreview }) {
  return (
    <div className="space-y-3">
      {/* El mosaico repetido 2 × 2: si deja costura, aquí se ve. */}
      <div
        role="img"
        aria-label="El mosaico repetido dos veces en cada dirección"
        className="aspect-square w-full rounded border border-ink-10"
        style={{
          backgroundImage: `url(${vista.mosaic_data_url})`,
          backgroundSize: '50% 50%',
          backgroundRepeat: 'repeat',
        }}
      />
      <p className="text-xs text-ink-60">
        Repetido 2 × 2. Junta medida:{' '}
        <span className="font-medium text-ink">{vista.seam.toFixed(2)}</span>{' '}
        {vista.seam_visible
          ? `— se nota (desde ${vista.seam_limit.toFixed(1)}).`
          : `— no se nota (por debajo de ${vista.seam_limit.toFixed(1)}).`}
      </p>
      {vista.warnings.length > 0 ? (
        <Notice title="La foto se puede mejorar">
          <ul className="list-disc space-y-1 pl-4 text-xs">
            {vista.warnings.map((aviso) => (
              <li key={aviso}>{aviso}</li>
            ))}
          </ul>
        </Notice>
      ) : (
        <p className="text-xs text-ink-60">La foto sirve: ni pequeña, ni movida, ni con luz desigual.</p>
      )}
    </div>
  )
}

function TarjetaDeTela({
  tela,
  onCambio,
  onFallo,
}: {
  tela: Fabric
  onCambio: () => void
  onFallo: (mensaje: string) => void
}) {
  const [editando, setEditando] = useState(false)
  const [nombre, setNombre] = useState(tela.name)
  const [composicion, setComposicion] = useState(tela.composition ?? '')
  const [repeticion, setRepeticion] = useState(tela.default_repeat)
  const [guardando, setGuardando] = useState(false)

  async function guardar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    setGuardando(true)
    try {
      await updateMyFabric(tela.id, {
        name: nombre.trim(),
        composition: composicion.trim() || null,
        default_repeat: repeticion,
      })
      setEditando(false)
      onCambio()
    } catch (causa) {
      onFallo(causa instanceof Error ? causa.message : 'No se pudo editar la tela.')
    } finally {
      setGuardando(false)
    }
  }

  async function borrar() {
    const ok = window.confirm(
      `¿Borrar «${tela.name}»? Si ya la probaste sobre alguna prenda, esas pruebas se conservan.`,
    )
    if (!ok) return
    try {
      await deleteMyFabric(tela.id)
      onCambio()
    } catch (causa) {
      onFallo(causa instanceof Error ? causa.message : 'No se pudo borrar la tela.')
    }
  }

  return (
    <li>
      <div
        className="aspect-square overflow-hidden rounded border border-ink-10"
        style={{ backgroundColor: tela.color_hex ?? '#f7f7f5' }}
      >
        {tela.texture_url && (
          <img src={tela.texture_url} alt={`Mosaico de ${tela.name}`} loading="lazy" className="h-full w-full object-cover" />
        )}
      </div>

      {editando ? (
        <form onSubmit={guardar} className="space-y-2 px-1 pt-3">
          <input
            aria-label="Nombre"
            value={nombre}
            maxLength={160}
            required
            onChange={(e) => setNombre(e.target.value)}
            className="campo"
          />
          <input
            aria-label="Composición"
            value={composicion}
            maxLength={160}
            placeholder="Composición"
            onChange={(e) => setComposicion(e.target.value)}
            className="campo"
          />
          <label className="flex items-center gap-2 text-xs text-ink-60">
            Repeticiones
            <input
              type="number"
              min={1}
              max={40}
              value={repeticion}
              onChange={(e) => setRepeticion(Math.min(40, Math.max(1, Number(e.target.value) || 1)))}
              className="campo w-20"
            />
          </label>
          <div className="flex gap-3">
            <button type="submit" className="text-xs font-medium underline underline-offset-4" disabled={guardando}>
              {guardando ? 'Guardando…' : 'Guardar'}
            </button>
            <button
              type="button"
              className="text-xs text-ink-60 underline underline-offset-4"
              onClick={() => setEditando(false)}
            >
              Cancelar
            </button>
          </div>
        </form>
      ) : (
        <div className="px-1 pt-3">
          <h3 className="truncate text-sm font-medium">{tela.name}</h3>
          <p className="mt-0.5 text-xs text-ink-60">
            {OWN_FABRIC_PATTERN_LABELS[tela.pattern as OwnFabricPattern] ?? tela.pattern} ·{' '}
            {tela.default_repeat} repeticiones
          </p>
          {tela.composition && <p className="text-xs text-ink-60">{tela.composition}</p>}
          <div className="mt-2 flex items-center gap-3">
            <button
              type="button"
              onClick={() => setEditando(true)}
              className="text-xs text-ink underline underline-offset-4"
            >
              Editar
            </button>
            <button
              type="button"
              onClick={borrar}
              className="text-xs text-ink-60 underline underline-offset-4 hover:text-ink"
            >
              Borrar
            </button>
          </div>
        </div>
      )}
    </li>
  )
}

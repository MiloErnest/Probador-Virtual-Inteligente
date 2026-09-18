/**
 * Mi taller: las prendas que ha subido el usuario.
 *
 * LA DECISIÓN FOTO/BOCETO SE PIDE AL SUBIR, Y SE EXPLICA
 * ------------------------------------------------------
 * No es una etiqueta para ordenar la galería: decide qué motor puede vestir la
 * prenda, y de ahí sale que la prueba sea gratis e instantánea o que cueste
 * dinero y tarde medio minuto. Preguntarlo sin explicarlo llevaría a que la
 * gente marcara «boceto» en una foto y se gastara el presupuesto sin saberlo.
 */

import { useCallback, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { Link } from 'react-router-dom'

import { EmptyBlock, ErrorBlock, LoadingBlock, Notice } from '@/components/StateBlocks'
import { useApi } from '@/hooks/useApi'
import { deleteGarmentUpload, fetchGarmentUploads, uploadGarment } from '@/services/endpoints'
import { GARMENT_KIND_LABELS, type GarmentKind, type GarmentUpload } from '@/types'

export default function TallerPage() {
  const fetcher = useCallback((signal: AbortSignal) => fetchGarmentUploads(signal), [])
  const { data, loading, error, reload } = useApi(fetcher)

  const [nombre, setNombre] = useState('')
  const [tipo, setTipo] = useState<GarmentKind>('photo')
  const [archivo, setArchivo] = useState<File | null>(null)
  const [subiendo, setSubiendo] = useState(false)
  const [fallo, setFallo] = useState<string | null>(null)
  const entradaRef = useRef<HTMLInputElement | null>(null)

  async function subir(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    if (archivo === null) return

    setFallo(null)
    setSubiendo(true)
    try {
      await uploadGarment(nombre.trim() || archivo.name, tipo, archivo)
      setNombre('')
      setArchivo(null)
      if (entradaRef.current) entradaRef.current.value = ''
      reload()
    } catch (causa) {
      setFallo(causa instanceof Error ? causa.message : 'No se pudo subir la prenda.')
    } finally {
      setSubiendo(false)
    }
  }

  async function borrar(id: number) {
    try {
      await deleteGarmentUpload(id)
      reload()
    } catch (causa) {
      setFallo(causa instanceof Error ? causa.message : 'No se pudo borrar.')
    }
  }

  return (
    <div className="wrap space-y-10">
      <header>
        <p className="rotulo">Mi taller</p>
        <div className="mt-4 border-b border-ink-10 pb-6">
          <h1 className="font-display text-titulo">Tus prendas</h1>
          <p className="mt-2 max-w-xl text-sm leading-relaxed text-ink-60">
            Sube la fotografía de una prenda o el boceto de un diseño, y pruébale telas del
            catálogo sin gastar ni un metro.
          </p>
        </div>
      </header>

      {fallo && <ErrorBlock title="Algo ha fallado" detail={fallo} />}

      <section className="grid gap-8 lg:grid-cols-[360px_minmax(0,1fr)] lg:gap-12">
        <form onSubmit={subir} className="space-y-5 rounded border border-ink-10 p-6">
          <h2 className="rotulo">Subir una prenda</h2>

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
              placeholder="Camisa de lino, modelo 3"
              className="campo"
            />
          </div>

          <fieldset className="space-y-2">
            <legend className="text-sm font-medium">Qué estás subiendo</legend>
            <TipoDePrenda
              valor="photo"
              actual={tipo}
              onChange={setTipo}
              titulo="Una fotografía"
              detalle="La foto ya tiene pliegues y sombras: la tela los reutiliza. Es instantáneo, gratis, y sale igual cada vez."
            />
            <TipoDePrenda
              valor="sketch"
              actual={tipo}
              onChange={setTipo}
              titulo="Un boceto"
              detalle="Un dibujo no tiene sombras que reutilizar, así que hay que generar la imagen con IA. Tarda y consume presupuesto."
            />
          </fieldset>

          <div className="space-y-1.5">
            <label htmlFor="archivo" className="block text-sm font-medium">
              Imagen
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
              Sobre fondo liso y que contraste con la prenda. Si la prenda es casi del
              color del fondo, no se puede recortar y te avisaremos.
            </p>
          </div>

          <button type="submit" className="btn-primary w-full" disabled={subiendo || !archivo}>
            {subiendo ? 'Subiendo y recortando…' : 'Subir'}
          </button>
        </form>

        <div className="space-y-6">
          {loading && <LoadingBlock label="Cargando tus prendas…" />}

          {error && !loading && <ErrorBlock title="No se pudieron cargar" detail={error} />}

          {!loading && !error && data?.length === 0 && (
            <EmptyBlock
              title="Todavía no has subido nada"
              detail="Sube una fotografía o un boceto para empezar a probar telas."
            />
          )}

          {!loading && !error && data && data.length > 0 && (
            <ul className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3">
              {data.map((prenda) => (
                <TarjetaDePrenda key={prenda.id} prenda={prenda} onBorrar={borrar} />
              ))}
            </ul>
          )}
        </div>
      </section>
    </div>
  )
}

function TipoDePrenda({
  valor,
  actual,
  onChange,
  titulo,
  detalle,
}: {
  valor: GarmentKind
  actual: GarmentKind
  onChange: (v: GarmentKind) => void
  titulo: string
  detalle: string
}) {
  const elegido = actual === valor
  return (
    <label
      className={`flex cursor-pointer gap-3 rounded border p-3 transition ${
        elegido ? 'border-ink bg-bone' : 'border-ink-10 hover:border-ink-40'
      }`}
    >
      <input
        type="radio"
        name="tipo"
        value={valor}
        checked={elegido}
        onChange={() => onChange(valor)}
        className="mt-1 accent-[#0A0A0B]"
      />
      <span>
        <span className="block text-sm font-medium">{titulo}</span>
        <span className="mt-0.5 block text-xs leading-relaxed text-ink-60">{detalle}</span>
      </span>
    </label>
  )
}

function TarjetaDePrenda({
  prenda,
  onBorrar,
}: {
  prenda: GarmentUpload
  onBorrar: (id: number) => void
}) {
  return (
    <li className="group">
      <Link to={`/taller/${prenda.id}`} className="block">
        <div className="relative aspect-[4/5] overflow-hidden rounded border border-ink-10 bg-bone">
          {prenda.image_url && (
            <img
              src={prenda.image_url}
              alt={prenda.name}
              loading="lazy"
              className="h-full w-full object-contain transition-transform duration-500 group-hover:scale-[1.03]"
            />
          )}
          <span className="pill absolute left-2 top-2 bg-paper/90 backdrop-blur">
            {GARMENT_KIND_LABELS[prenda.kind]}
          </span>
        </div>
      </Link>

      <div className="px-1 pt-3">
        <h3 className="truncate text-sm font-medium">{prenda.name}</h3>
        <div className="mt-2 flex items-center gap-3">
          <Link to={`/taller/${prenda.id}`} className="text-xs text-ink underline underline-offset-4">
            Probar telas
          </Link>
          <button
            type="button"
            onClick={() => onBorrar(prenda.id)}
            className="text-xs text-ink-60 underline underline-offset-4 hover:text-ink"
          >
            Borrar
          </button>
        </div>

        {prenda.mask_warning && (
          <div className="mt-3">
            <Notice title="El recorte no ha salido bien">
              <p className="text-xs">{prenda.mask_warning}</p>
            </Notice>
          </div>
        )}
      </div>
    </li>
  )
}

import { Link } from 'react-router-dom'

import { CATEGORY_LABELS, FABRIC_LABELS, type Garment } from '@/types'

interface Props {
  garment: Garment
  /** Enlaza al probador con la prenda ya elegida. */
  probable?: boolean
}

export default function GarmentCard({ garment, probable = false }: Props) {
  const contenido = (
    <>
      <div className="relative aspect-[3/4] overflow-hidden bg-bone">
        {garment.image_url ? (
          <img
            src={garment.image_url}
            alt={garment.name}
            loading="lazy"
            className="h-full w-full object-cover transition-transform duration-700 ease-out group-hover:scale-[1.04]"
          />
        ) : (
          // El catálogo puede sembrarse sin fotos: el marcador evita huecos
          // rotos y comunica que falta subir la imagen.
          <div className="flex h-full w-full items-center justify-center">
            <span className="font-display text-5xl text-ink-20">
              {garment.name.charAt(0).toUpperCase()}
            </span>
          </div>
        )}

        {probable && (
          // Aparece al pasar por encima. En un móvil no hay "encima", así que
          // en pantallas táctiles se muestra siempre.
          <span className="pointer-events-none absolute inset-x-3 bottom-3 flex items-center justify-center rounded-full bg-ink px-4 py-2 text-xs font-medium text-paper opacity-100 transition-all duration-300 sm:translate-y-2 sm:opacity-0 sm:group-hover:translate-y-0 sm:group-hover:opacity-100">
            Probármela
          </span>
        )}
      </div>

      <div className="flex items-start justify-between gap-3 px-1 pt-3">
        <div className="min-w-0">
          <h3 className="truncate text-sm font-medium">{garment.name}</h3>
          <p className="mt-0.5 text-xs text-ink-60">
            {CATEGORY_LABELS[garment.category]}
            {garment.fabric && ` · ${FABRIC_LABELS[garment.fabric]}`}
          </p>
        </div>
      </div>
    </>
  )

  if (!probable) {
    return <article className="group">{contenido}</article>
  }

  return (
    <Link to={`/probador?prenda=${garment.id}`} className="group block">
      {contenido}
    </Link>
  )
}

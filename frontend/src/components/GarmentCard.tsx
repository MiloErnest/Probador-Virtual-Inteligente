import { CATEGORY_LABELS, type Garment } from '@/types'

interface Props {
  garment: Garment
}

export default function GarmentCard({ garment }: Props) {
  return (
    <article className="card group overflow-hidden">
      <div className="relative aspect-[3/4] overflow-hidden bg-gradient-to-br from-accent-soft to-canvas">
        {garment.image_url ? (
          <img
            src={garment.image_url}
            alt={garment.name}
            loading="lazy"
            className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-[1.03]"
          />
        ) : (
          // El catálogo inicial se siembra sin fotos: el marcador evita huecos
          // rotos y comunica que falta subir la imagen.
          <div className="flex h-full w-full items-center justify-center">
            <span className="font-display text-3xl text-ink-muted/40">
              {garment.name.charAt(0).toUpperCase()}
            </span>
          </div>
        )}
        <span className="pill absolute left-3 top-3 bg-white/85 text-ink-soft backdrop-blur">
          {CATEGORY_LABELS[garment.category]}
        </span>
      </div>

      <div className="space-y-1 p-4">
        <h3 className="font-display text-base leading-snug">{garment.name}</h3>
        {garment.description && (
          <p className="line-clamp-2 text-sm text-ink-muted">{garment.description}</p>
        )}
      </div>
    </article>
  )
}

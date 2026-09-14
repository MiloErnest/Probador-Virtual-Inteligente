/**
 * Portada.
 *
 * Antes era una hoja de ruta de cinco fases con cuatro de ellas en
 * "planificado". Eso describía el plan de trabajo, no el producto: quien abría
 * la aplicación se encontraba un índice de cosas que no podía hacer.
 *
 * Ahora enseña lo único que hace, y lo enseña con las prendas reales del
 * catálogo. La franja de fotos no es decoración: es la prueba de que el
 * backend responde y de que hay ropa que probarse.
 */

import { useCallback } from 'react'
import { Link } from 'react-router-dom'

import { useAuth } from '@/auth/AuthContext'
import { useApi } from '@/hooks/useApi'
import { fetchGarments } from '@/services/endpoints'

const PASOS = [
  {
    titulo: 'Elige una prenda',
    detalle:
      'Del catálogo. Se recorta su fondo en tu navegador para poder superponerla sin el rectángulo de la foto.',
  },
  {
    titulo: 'Ponte delante de la cámara',
    detalle:
      'Un modelo de detección de pose localiza tus hombros, caderas y piernas, y mide tu silueta real.',
  },
  {
    titulo: 'La prenda se adapta',
    detalle:
      'Se parte en franjas y cada una sigue tu cuerpo: se estrecha en la cintura, gira si te inclinas y mide lo que tiene que medir.',
  },
]

export default function HomePage() {
  const { isAuthenticated } = useAuth()

  const fetcher = useCallback((signal: AbortSignal) => fetchGarments({ signal }), [])
  const { data } = useApi(fetcher)
  const conFoto = (data ?? []).filter((g) => g.image_url !== null).slice(0, 6)

  return (
    <div className="space-y-20 sm:space-y-28">
      <section className="wrap">
        <p className="rotulo">Vestidor inteligente</p>

        <h1 className="mt-5 max-w-[13ch] font-display text-display">
          Pruébate la ropa sin quitarte la que llevas.
        </h1>

        <div className="mt-8 flex flex-col gap-8 border-t border-ink-10 pt-8 sm:flex-row sm:items-start sm:justify-between">
          <p className="max-w-lg text-base leading-relaxed text-ink-80">
            Abre la cámara, elige una prenda del catálogo y mírate con ella puesta. Todo ocurre
            dentro de tu navegador: tu imagen no se envía a ningún servidor ni se guarda en
            ninguna parte.
          </p>

          <div className="flex shrink-0 flex-wrap gap-3">
            <Link to={isAuthenticated ? '/probador' : '/entrar'} className="btn-primary">
              Abrir el probador
            </Link>
            <Link to="/catalogo" className="btn-ghost">
              Ver el catálogo
            </Link>
          </div>
        </div>
      </section>

      {conFoto.length > 0 && (
        // Se sale del contenedor a propósito y se desplaza de lado en móvil:
        // una fila de ropa cortada por el borde invita a seguir mirando, y
        // apilarla en vertical rompería el ritmo de la portada.
        <section aria-label="Prendas del catálogo" className="-mt-6 sm:-mt-10">
          <div className="flex snap-x snap-mandatory gap-3 overflow-x-auto px-5 pb-2 sm:gap-4 sm:px-8 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
            {conFoto.map((prenda) => (
              <Link
                key={prenda.id}
                to="/catalogo"
                className="group w-[46%] shrink-0 snap-start sm:w-[30%] lg:w-[18%]"
              >
                <div className="aspect-[3/4] overflow-hidden bg-bone">
                  <img
                    src={prenda.image_url as string}
                    alt={prenda.name}
                    loading="lazy"
                    className="h-full w-full object-cover transition-transform duration-700 ease-out group-hover:scale-105"
                  />
                </div>
                <p className="mt-2 truncate text-xs text-ink-60">{prenda.name}</p>
              </Link>
            ))}
          </div>
        </section>
      )}

      <section className="sobre-negro bg-ink py-16 text-paper sm:py-24">
        <div className="wrap">
          <p className="rotulo text-paper/50">Cómo funciona</p>

          <ol className="mt-10 grid gap-px border-t border-paper/15 sm:grid-cols-3">
            {PASOS.map((paso, i) => (
              <li key={paso.titulo} className="border-b border-paper/15 py-8 sm:border-b-0 sm:pr-8">
                <span className="font-display text-5xl text-paper/25">
                  {String(i + 1).padStart(2, '0')}
                </span>
                <h3 className="mt-4 text-base font-medium">{paso.titulo}</h3>
                <p className="mt-2 max-w-xs text-sm leading-relaxed text-paper/60">
                  {paso.detalle}
                </p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <section className="wrap">
        <div className="grid gap-10 border-t border-ink-10 pt-10 sm:grid-cols-[1fr_1.4fr] sm:gap-16">
          <div>
            <p className="rotulo">Hasta dónde llega</p>
            <h2 className="mt-4 font-display text-titulo">Lo que ves es una superposición.</h2>
          </div>

          <div className="space-y-5 text-sm leading-relaxed text-ink-80">
            <p>
              La prenda se deforma para seguir tu cuerpo, pero no se simula la tela: no hay
              pliegues, ni sombras propias, ni peso. Una camisa no ondea. Es una vista previa de
              corte y proporción, no una fotografía de cómo te quedaría.
            </p>
            <p>
              El tejido de cada prenda —algodón, cuero, punto— sí cambia algo: cuánto se ciñe al
              contorno. Un cuero mantiene su forma; un punto fino se pega. Es un ajuste de
              silueta, y es lo más honesto que se puede hacer sin simular el material.
            </p>
            <p className="text-ink-60">
              La simulación de telas y la caída real del tejido son el paso siguiente, y llevan
              un motor 3D detrás.
            </p>
          </div>
        </div>
      </section>
    </div>
  )
}

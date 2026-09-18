/**
 * Portada.
 *
 * Cuenta el producto del Product Vision Board: una herramienta para que
 * diseñadores, modistas y talleres vean su prenda con distintas telas antes de
 * comprar el metraje. El usuario no es quien se pone la ropa: es quien tiene
 * que elegir la tela.
 *
 * La franja de telas no es decoración, es la prueba de que el backend responde
 * y de que hay catálogo. Y enseña el tejido de cerca, que es lo que se compra.
 */

import { useCallback } from 'react'
import { Link } from 'react-router-dom'

import { useAuth } from '@/auth/AuthContext'
import { useApi } from '@/hooks/useApi'
import { fetchFabrics } from '@/services/endpoints'

const PASOS = [
  {
    titulo: 'Sube tu prenda',
    detalle:
      'La fotografía de una prenda que ya existe, o el boceto de una que todavía no. Se recorta del fondo automáticamente.',
  },
  {
    titulo: 'Elige telas del catálogo',
    detalle:
      'Con su ficha real: composición, gramaje, ancho del rollo y precio por metro. Lo que hace falta para decidir.',
  },
  {
    titulo: 'Compara y decide',
    detalle:
      'Todas las opciones a la vez, sobre tu diseño. Sin pedir muestras, sin esperar días y sin gastar tela.',
  },
]

export default function HomePage() {
  const { isAuthenticated } = useAuth()

  const fetcher = useCallback(
    (signal: AbortSignal) => fetchFabrics({ onlyProbable: true, signal }),
    [],
  )
  const { data } = useApi(fetcher)
  const telas = (data ?? []).slice(0, 8)

  return (
    <div className="space-y-20 sm:space-y-28">
      <section className="wrap">
        <p className="rotulo">Prueba virtual de telas</p>

        <h1 className="mt-5 max-w-[15ch] font-display text-display">
          Mira tu diseño con otra tela. Sin cortar ni un metro.
        </h1>

        <div className="mt-8 flex flex-col gap-8 border-t border-ink-10 pt-8 sm:flex-row sm:items-start sm:justify-between">
          <p className="max-w-lg text-base leading-relaxed text-ink-80">
            Hoy, para saber cómo queda una prenda en una tela hay que pedir muestras y
            probarlas una por una. Eso cuesta tiempo, dinero y material. Aquí subes tu
            prenda, eliges telas del catálogo y las comparas en minutos.
          </p>

          <div className="flex shrink-0 flex-wrap gap-3">
            <Link to={isAuthenticated ? '/taller' : '/entrar'} className="btn-primary">
              {isAuthenticated ? 'Ir a mi taller' : 'Empezar'}
            </Link>
            <Link to="/telas" className="btn-ghost">
              Ver las telas
            </Link>
          </div>
        </div>
      </section>

      {telas.length > 0 && (
        <section aria-label="Telas del catálogo" className="-mt-6 sm:-mt-10">
          <div className="flex snap-x snap-mandatory gap-3 overflow-x-auto px-5 pb-2 sm:gap-4 sm:px-8 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
            {telas.map((tela) => (
              <Link
                key={tela.id}
                to="/telas"
                className="group w-[40%] shrink-0 snap-start sm:w-[24%] lg:w-[15%]"
              >
                <div
                  className="aspect-square overflow-hidden rounded border border-ink-10"
                  style={{ backgroundColor: tela.color_hex ?? '#f7f7f5' }}
                >
                  {tela.texture_url && (
                    <img
                      src={tela.texture_url}
                      alt={tela.name}
                      loading="lazy"
                      className="h-full w-full object-cover transition-transform duration-700 ease-out group-hover:scale-110"
                    />
                  )}
                </div>
                <p className="mt-2 truncate text-xs text-ink-60">{tela.name}</p>
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
            <p className="rotulo">Cómo se hace</p>
            <h2 className="mt-4 font-display text-titulo">
              Los pliegues son los de tu foto.
            </h2>
          </div>

          <div className="space-y-5 text-sm leading-relaxed text-ink-80">
            <p>
              Una fotografía ya contiene lo difícil: dónde hay un pliegue, dónde da la luz,
              dónde cae una sombra. Esa información depende de la <em>forma</em> de la
              prenda, no de su color, así que se puede separar y reutilizar con otra tela.
            </p>
            <p>
              Por eso el resultado no es una tela pegada encima: cae por donde caía la
              original, respeta las costuras y los botones, y el estampado se dobla con los
              pliegues. Es instantáneo, no cuesta nada, y sale idéntico cada vez — que es lo
              único que hace honesta una comparación entre cuatro telas.
            </p>
            <p>
              <strong className="font-medium">Con un boceto es otra cosa.</strong> Un dibujo
              de líneas no tiene sombras que reutilizar: el volumen y la caída hay que
              inventarlos, y ahí sí entra la inteligencia artificial generativa.
            </p>
            <p className="text-ink-60">
              Lo que no hace, y conviene saberlo: no cambia cómo <em>cae</em> la tela. Si la
              foto es de un vestido fluido, una lona rígida caerá como el vestido. Simular el
              tejido es otro problema, y bastante mayor.
            </p>
          </div>
        </div>
      </section>
    </div>
  )
}

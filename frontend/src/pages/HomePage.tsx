import { Link } from 'react-router-dom'

const ROADMAP = [
  { phase: 1, title: 'Probador virtual 2D', detail: 'Foto + prenda → resultado generado por IA.', state: 'En curso' },
  { phase: 2, title: 'Diseño con lenguaje natural', detail: 'Describir una prenda y generarla.', state: 'Planificado' },
  { phase: 3, title: 'Análisis corporal', detail: 'Pose, medidas aproximadas y talla.', state: 'Planificado' },
  { phase: 4, title: 'Modelos 3D y telas', detail: 'Avatar, materiales PBR y caída del tejido.', state: 'Planificado' },
  { phase: 5, title: 'Realidad aumentada', detail: 'Cámara en vivo, tracking y oclusión.', state: 'Planificado' },
]

export default function HomePage() {
  return (
    <div className="space-y-16">
      <section className="max-w-3xl">
        <span className="pill bg-accent-soft text-accent">Etapa 1 · Infraestructura base</span>
        <h1 className="mt-5 font-display text-4xl leading-[1.1] sm:text-5xl">
          Prueba, diseña y visualiza prendas sin llegar a ponértelas.
        </h1>
        <p className="mt-5 text-base leading-relaxed text-ink-soft">
          Una plataforma que combina inteligencia artificial generativa, visión por computador,
          modelado 3D y realidad aumentada para ver cómo te queda una prenda —incluso una que
          todavía no existe.
        </p>
        <div className="mt-8 flex flex-wrap gap-3">
          <Link to="/catalogo" className="btn-primary">
            Ver el catálogo
          </Link>
          <Link to="/probador" className="btn-ghost">
            Probador virtual
          </Link>
        </div>
      </section>

      <section>
        <h2 className="font-display text-2xl">Hoja de ruta</h2>
        <p className="mt-2 max-w-2xl text-sm text-ink-muted">
          El sistema se construye por fases. Cada una deja el proyecto funcionando antes de empezar
          la siguiente.
        </p>

        <ol className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {ROADMAP.map((item) => (
            <li key={item.phase} className="card p-5">
              <div className="flex items-center justify-between">
                <span className="font-display text-2xl text-ink-muted/50">
                  {String(item.phase).padStart(2, '0')}
                </span>
                <span
                  className={`pill ${
                    item.state === 'En curso'
                      ? 'bg-accent-soft text-accent'
                      : 'bg-black/[0.05] text-ink-muted'
                  }`}
                >
                  {item.state}
                </span>
              </div>
              <h3 className="mt-3 text-sm font-medium">{item.title}</h3>
              <p className="mt-1 text-sm text-ink-muted">{item.detail}</p>
            </li>
          ))}
        </ol>
      </section>
    </div>
  )
}

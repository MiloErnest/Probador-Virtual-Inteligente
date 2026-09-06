import { PhaseNotice } from '@/components/StateBlocks'

const EXAMPLE =
  'Genera un vestido largo de gala color rojo, con mangas transparentes, escote en V y falda amplia.'

export default function DesignAIPage() {
  return (
    <div className="max-w-3xl space-y-6">
      <header>
        <h1 className="font-display text-3xl">Diseñar con IA</h1>
        <p className="mt-1.5 text-sm text-ink-muted">
          Describe una prenda con tus palabras y conviértela en un diseño que puedas probarte.
        </p>
      </header>

      <PhaseNotice phase={2} title="Aún no disponible">
        <p>
          Esta sección pertenece a la Fase 2. El flujo previsto es: texto del usuario → un modelo de
          lenguaje extrae atributos estructurados (silueta, largo, escote, manga, color, tejido) →
          un modelo de difusión genera la prenda → esa prenda entra directamente en el probador.
        </p>
        <figure className="rounded-lg border border-black/[0.07] bg-canvas p-4">
          <figcaption className="mb-1.5 text-xs uppercase tracking-wider text-ink-muted">
            Ejemplo de instrucción
          </figcaption>
          <blockquote className="font-display text-base text-ink">“{EXAMPLE}”</blockquote>
        </figure>
        <p>
          No se activará hasta que la Fase 1 (probador con foto real) funcione de principio a fin.
        </p>
      </PhaseNotice>
    </div>
  )
}

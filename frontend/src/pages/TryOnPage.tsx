import { Link } from 'react-router-dom'

import { PhaseNotice } from '@/components/StateBlocks'

export default function TryOnPage() {
  return (
    <div className="max-w-3xl space-y-6">
      <header>
        <h1 className="font-display text-3xl">Probador virtual</h1>
        <p className="mt-1.5 text-sm text-ink-muted">
          Sube una foto, elige una prenda y deja que la IA genere el resultado.
        </p>
      </header>

      <PhaseNotice phase={1} title="Pendiente de la integración con IA">
        <p>
          La infraestructura ya está lista: hay catálogo, almacenamiento de imágenes y la tabla de
          sesiones de prueba. Falta conectar el proveedor de Virtual Try-On.
        </p>
        <p>Lo siguiente que se implementará en esta pantalla:</p>
        <ul className="list-disc space-y-1 pl-5">
          <li>Autenticación con JWT (para saber de quién es cada prueba).</li>
          <li>Subida de la fotografía del usuario.</li>
          <li>Selección de prenda del catálogo.</li>
          <li>Llamada al modelo de try-on y guardado del resultado.</li>
        </ul>
        <p>
          Mientras tanto puedes revisar el{' '}
          <Link to="/catalogo" className="underline underline-offset-2">
            catálogo
          </Link>
          .
        </p>
      </PhaseNotice>
    </div>
  )
}

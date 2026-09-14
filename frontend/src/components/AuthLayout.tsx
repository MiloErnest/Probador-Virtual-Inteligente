/**
 * Marco compartido por entrar y registrarse.
 *
 * Un formulario de cuatro campos centrado en una página en blanco se ve
 * pequeño y sin terminar. Partiendo la pantalla —un panel negro con el lema y
 * el formulario al lado— la página tiene peso, y el panel además explica de
 * paso para qué sirve la cuenta, que es justo lo que uno se pregunta antes de
 * escribir su correo.
 *
 * En móvil el panel se reduce a una franja: ahí el espacio es del formulario.
 */

import type { ReactNode } from 'react'

interface Props {
  titulo: string
  lema: string
  children: ReactNode
}

export default function AuthLayout({ titulo, lema, children }: Props) {
  return (
    <div className="wrap">
      <div className="grid overflow-hidden rounded-marco border border-ink-10 lg:grid-cols-2">
        <div className="sobre-negro flex flex-col justify-between gap-10 bg-ink p-8 text-paper sm:p-10 lg:p-12">
          <p className="rotulo text-paper/50">{titulo}</p>

          <p className="max-w-sm font-display text-[clamp(1.5rem,3vw,2.25rem)] leading-[1.15]">
            {lema}
          </p>

          <p className="hidden text-xs leading-relaxed text-paper/40 lg:block">
            El probador funciona entero dentro de tu navegador. La cuenta existe para saber
            quién entra, no para recoger nada tuyo.
          </p>
        </div>

        <div className="bg-paper p-8 sm:p-10 lg:p-12">
          <div className="mx-auto max-w-sm">{children}</div>
        </div>
      </div>
    </div>
  )
}

/**
 * Lleva al ancla de la URL (`/telas#mis-telas`, `/taller/4#comparar`) cuando
 * la página ya tiene su contenido.
 *
 * El navegador salta al ancla al cargar, pero aquí el contenido llega después,
 * de la API: el salto se hacía con la página casi vacía y, al llegar el
 * catálogo, la sección quedaba muy por debajo. `listo` dice cuándo ya está todo
 * lo que va ENCIMA de la sección, y se salta una sola vez.
 */

import { useEffect, useRef } from 'react'
import { useLocation } from 'react-router-dom'

export function useAncla(listo: boolean) {
  const { hash } = useLocation()
  const hecho = useRef<string | null>(null)

  useEffect(() => {
    if (!listo || !hash || hecho.current === hash) return
    // Un fotograma después, para que el contenido recién llegado ya esté pintado.
    const id = window.requestAnimationFrame(() => {
      const destino = document.getElementById(decodeURIComponent(hash.slice(1)))
      if (destino) {
        destino.scrollIntoView({ block: 'start' })
        hecho.current = hash
      }
    })
    return () => window.cancelAnimationFrame(id)
  }, [listo, hash])
}

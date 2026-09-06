/**
 * Hook genérico para leer datos de la API.
 *
 * Cubre lo que necesitamos ahora: estado de carga, error y recarga manual,
 * cancelando la petición si el componente se desmonta. Cuando aparezcan
 * necesidades reales de caché o revalidación, se sustituirá por TanStack
 * Query; añadirla hoy sería complejidad sin uso.
 */

import { useCallback, useEffect, useState } from 'react'

interface ApiState<T> {
  data: T | null
  loading: boolean
  error: string | null
}

export function useApi<T>(
  fetcher: (signal: AbortSignal) => Promise<T>,
  deps: unknown[] = [],
) {
  const [state, setState] = useState<ApiState<T>>({
    data: null,
    loading: true,
    error: null,
  })
  const [reloadToken, setReloadToken] = useState(0)

  const reload = useCallback(() => setReloadToken((token) => token + 1), [])

  useEffect(() => {
    const controller = new AbortController()
    let active = true

    setState((previous) => ({ ...previous, loading: true, error: null }))

    fetcher(controller.signal)
      .then((data) => {
        if (active) setState({ data, loading: false, error: null })
      })
      .catch((error: unknown) => {
        if (!active) return
        if (error instanceof DOMException && error.name === 'AbortError') return
        const message = error instanceof Error ? error.message : 'Error desconocido'
        setState({ data: null, loading: false, error: message })
      })

    return () => {
      active = false
      controller.abort()
    }
    // `fetcher` se recrea en cada render; las dependencias reales las declara
    // quien usa el hook.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, reloadToken])

  return { ...state, reload }
}

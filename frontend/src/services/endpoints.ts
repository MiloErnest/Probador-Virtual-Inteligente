/** Llamadas a la API agrupadas por recurso. */

import { api } from '@/services/apiClient'
import type { Garment, GarmentCategory, Health, TryOnSession } from '@/types'

export function fetchHealth(signal?: AbortSignal) {
  return api.get<Health>('/health', { signal })
}

export function fetchGarments(
  options: { category?: GarmentCategory; signal?: AbortSignal } = {},
) {
  return api.get<Garment[]>('/garments', {
    params: { category: options.category },
    signal: options.signal,
  })
}

export function fetchGarment(id: number, signal?: AbortSignal) {
  return api.get<Garment>(`/garments/${id}`, { signal })
}

export function fetchTryOnSessions(userId: number, signal?: AbortSignal) {
  return api.get<TryOnSession[]>('/try-on-sessions', {
    params: { user_id: userId },
    signal,
  })
}

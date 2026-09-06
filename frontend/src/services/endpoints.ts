/** Llamadas a la API agrupadas por recurso. */

import { api } from '@/services/apiClient'
import type { Garment, GarmentCategory, Health, TokenResponse, TryOnSession, User } from '@/types'

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

/**
 * Historial del usuario autenticado.
 *
 * Ya no recibe un `userId`: el backend lo deduce del token. Pasarlo por la
 * URL permitia leer el historial de cualquiera cambiando un numero.
 */
export function fetchTryOnSessions(signal?: AbortSignal) {
  return api.get<TryOnSession[]>('/try-on-sessions', { signal })
}

// --- Autenticacion ---

export function login(email: string, password: string) {
  return api.post<TokenResponse>('/auth/login', { email, password })
}

export function register(name: string, email: string, password: string) {
  return api.post<User>('/users', { name, email, password })
}

/** Quien soy, segun el token actual. Sirve para restaurar la sesion al cargar. */
export function fetchCurrentUser(signal?: AbortSignal) {
  return api.get<User>('/auth/me', { signal })
}

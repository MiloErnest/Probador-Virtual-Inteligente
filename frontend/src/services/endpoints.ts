/** Llamadas a la API agrupadas por recurso. */

import { api } from '@/services/apiClient'
import type {
  BodyMeasurements,
  BodyProfile,
  Design,
  Garment,
  GarmentCategory,
  Health,
  SizeRecommendation,
  TokenResponse,
  TryOnSession,
  User,
} from '@/types'

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

/** Una prueba concreta. Se usa para sondear su estado mientras se procesa. */
export function fetchTryOnSession(id: number, signal?: AbortSignal) {
  return api.get<TryOnSession>(`/try-on-sessions/${id}`, { signal })
}

/**
 * Crea una prueba virtual. Responde 202 con la prueba en estado `pending`:
 * el resultado NO viene aqui. Hay que sondear con `fetchTryOnSession` hasta
 * que el estado sea `completed` o `failed`.
 */
export function createTryOnSession(
  source: { garmentId: number } | { designId: number },
  photo: File,
  signal?: AbortSignal,
) {
  // El backend exige exactamente uno de los dos. El tipo de `source` lo
  // hace imposible de equivocar desde aqui.
  const fields: Record<string, string | number> =
    'garmentId' in source ? { garment_id: source.garmentId } : { design_id: source.designId }
  return api.postForm<TryOnSession>('/try-on-sessions', { photo }, fields, { signal })
}

/** Borra una prueba y sus imagenes del servidor. */
export function deleteTryOnSession(id: number, signal?: AbortSignal) {
  return api.delete<{ message: string }>(`/try-on-sessions/${id}`, { signal })
}

// --- Disenos (Fase 2) ---

export function fetchDesigns(signal?: AbortSignal) {
  return api.get<Design[]>('/designs', { signal })
}

export function fetchDesign(id: number, signal?: AbortSignal) {
  return api.get<Design>(`/designs/${id}`, { signal })
}

/** Responde 202 con el diseno en `pending`: hay que sondear con fetchDesign. */
export function createDesign(prompt: string, signal?: AbortSignal) {
  return api.post<Design>('/designs', { prompt }, { signal })
}

/** Crea una version nueva; el diseno original se conserva intacto. */
export function refineDesign(id: number, refinement: string, signal?: AbortSignal) {
  return api.post<Design>(`/designs/${id}/refine`, { refinement }, { signal })
}

// --- Perfil corporal y talla (Fase 3) ---

export function fetchBodyProfile(signal?: AbortSignal) {
  return api.get<BodyProfile>('/body-profile', { signal })
}

/** Actualizacion parcial: solo se tocan los campos que se envian. */
export function saveBodyProfile(measurements: BodyMeasurements, signal?: AbortSignal) {
  return api.put<BodyProfile>('/body-profile', measurements, { signal })
}

export function deleteBodyProfile(signal?: AbortSignal) {
  return api.delete<{ message: string }>('/body-profile', { signal })
}

/** Sincrono: el analisis tarda ~1 s, no hace falta sondear. */
export function analyseBodyPhoto(photo: File, heightCm?: number, signal?: AbortSignal) {
  const fields: Record<string, string | number> = heightCm !== undefined ? { height_cm: heightCm } : {}
  return api.postForm<BodyProfile>('/body-profile/analyse', { photo }, fields, { signal })
}

export function fetchSizeRecommendation(
  target: { garmentId: number } | { category: GarmentCategory },
  signal?: AbortSignal,
) {
  const params =
    'garmentId' in target ? { garment_id: target.garmentId } : { category: target.category }
  return api.get<SizeRecommendation>('/body-profile/size-recommendation', { params, signal })
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

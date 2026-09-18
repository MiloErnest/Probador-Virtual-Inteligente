/** Llamadas a la API agrupadas por recurso. */

import { api } from '@/services/apiClient'
import type {
  Fabric,
  FabricPattern,
  Garment,
  GarmentCategory,
  GarmentKind,
  GarmentUpload,
  Health,
  TokenResponse,
  Trial,
  TrialMethod,
  User,
} from '@/types'

export function fetchHealth(signal?: AbortSignal) {
  return api.get<Health>('/health', { signal })
}

// --- Catálogo de telas ------------------------------------------------------

export function fetchFabrics(
  options: {
    pattern?: FabricPattern
    /** Solo las que tienen mosaico y por tanto se pueden probar. */
    onlyProbable?: boolean
    signal?: AbortSignal
  } = {},
) {
  return api.get<Fabric[]>('/fabrics', {
    params: {
      pattern: options.pattern,
      only_probable: options.onlyProbable ? true : undefined,
    },
    signal: options.signal,
  })
}

export function fetchFabric(id: number, signal?: AbortSignal) {
  return api.get<Fabric>(`/fabrics/${id}`, { signal })
}

// --- Mis prendas ------------------------------------------------------------

export function fetchGarmentUploads(signal?: AbortSignal) {
  return api.get<GarmentUpload[]>('/garment-uploads', { signal })
}

export function fetchGarmentUpload(id: number, signal?: AbortSignal) {
  return api.get<GarmentUpload>(`/garment-uploads/${id}`, { signal })
}

/**
 * Sube una prenda. `kind` no es una etiqueta: decide qué motor puede vestirla.
 * Una fotografía trae su propia luz; un boceto hay que inventárselo con IA.
 */
export function uploadGarment(
  name: string,
  kind: GarmentKind,
  file: File,
  signal?: AbortSignal,
) {
  return api.postForm<GarmentUpload>('/garment-uploads', { file }, { name, kind }, { signal })
}

export function deleteGarmentUpload(id: number, signal?: AbortSignal) {
  return api.delete<{ message: string }>(`/garment-uploads/${id}`, { signal })
}

// --- Pruebas de tela --------------------------------------------------------

export function fetchTrials(
  options: { garmentUploadId?: number; signal?: AbortSignal } = {},
) {
  return api.get<Trial[]>('/trials', {
    params: { garment_upload_id: options.garmentUploadId },
    signal: options.signal,
  })
}

export function fetchTrial(id: number, signal?: AbortSignal) {
  return api.get<Trial>(`/trials/${id}`, { signal })
}

/**
 * Lanza una prueba. Responde 202 con la prueba en `pending`: **el resultado no
 * viene aquí**. Hay que sondear con `fetchTrial` hasta `completed` o `failed`.
 */
export function createTrial(
  input: {
    garmentUploadId: number
    fabricId: number
    method?: TrialMethod
    repeatAcross?: number
  },
  signal?: AbortSignal,
) {
  return api.post<Trial>(
    '/trials',
    {
      garment_upload_id: input.garmentUploadId,
      fabric_id: input.fabricId,
      method: input.method,
      repeat_across: input.repeatAcross,
    },
    { signal },
  )
}

export function deleteTrial(id: number, signal?: AbortSignal) {
  return api.delete<{ message: string }>(`/trials/${id}`, { signal })
}

// --- Probador con cámara ----------------------------------------------------

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

// --- Autenticación ----------------------------------------------------------

export function login(email: string, password: string) {
  return api.post<TokenResponse>('/auth/login', { email, password })
}

export function register(name: string, email: string, password: string) {
  return api.post<User>('/users', { name, email, password })
}

/** Quién soy, según el token actual. Restaura la sesión al cargar. */
export function fetchCurrentUser(signal?: AbortSignal) {
  return api.get<User>('/auth/me', { signal })
}

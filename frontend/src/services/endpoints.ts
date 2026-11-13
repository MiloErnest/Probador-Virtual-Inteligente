/** Llamadas a la API agrupadas por recurso. */

import { api } from '@/services/apiClient'
import type {
  Fabric,
  FabricPattern,
  FabricPreview,
  OwnFabricCreated,
  OwnFabricPattern,
  GarmentCategory,
  GarmentKind,
  GarmentUpload,
  Health,
  PersonPhoto,
  TokenResponse,
  Trial,
  TryOn,
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

// --- Mis telas: las que el usuario fotografía en su taller -----------------

/**
 * `includeRetired` trae también las borradas que tienen pruebas: el historial
 * sigue necesitando su nombre, aunque ya no se puedan elegir.
 */
export function fetchMyFabrics(options: { includeRetired?: boolean; signal?: AbortSignal } = {}) {
  return api.get<Fabric[]>('/my-fabrics', {
    params: { include_retired: options.includeRetired ? true : undefined },
    signal: options.signal,
  })
}

/**
 * Catálogo + mis telas, para elegir con qué probar. Las mías van primero:
 * quien sube una tela es para probarla.
 */
export async function fetchFabricsToTry(signal?: AbortSignal) {
  const [mias, catalogo] = await Promise.all([
    fetchMyFabrics({ includeRetired: true, signal }),
    fetchFabrics({ signal }),
  ])
  return [...mias, ...catalogo]
}

/** El mosaico que saldría de la foto. No guarda nada. */
export function previewMyFabric(pattern: OwnFabricPattern, file: File, signal?: AbortSignal) {
  return api.postForm<FabricPreview>('/my-fabrics/preview', { file }, { pattern }, { signal })
}

export function createMyFabric(
  input: {
    name: string
    pattern: OwnFabricPattern
    file: File
    composition?: string
    defaultRepeat?: number
  },
  signal?: AbortSignal,
) {
  const fields: Record<string, string | number> = { name: input.name, pattern: input.pattern }
  if (input.composition) fields.composition = input.composition
  if (input.defaultRepeat) fields.default_repeat = input.defaultRepeat
  return api.postForm<OwnFabricCreated>('/my-fabrics', { file: input.file }, fields, { signal })
}

export function updateMyFabric(
  id: number,
  changes: { name?: string; composition?: string | null; default_repeat?: number },
  signal?: AbortSignal,
) {
  return api.patch<Fabric>(`/my-fabrics/${id}`, changes, { signal })
}

/** Si la tela tiene pruebas, se retira y las pruebas se conservan. */
export function deleteMyFabric(id: number, signal?: AbortSignal) {
  return api.delete<void>(`/my-fabrics/${id}`, { signal })
}

// --- Mis prendas ------------------------------------------------------------

export function fetchGarmentUploads(signal?: AbortSignal) {
  return api.get<GarmentUpload[]>('/garment-uploads', { signal })
}

export function fetchGarmentUpload(id: number, signal?: AbortSignal) {
  return api.get<GarmentUpload>(`/garment-uploads/${id}`, { signal })
}

/**
 * Sube una prenda. Una fotografía vuelve lista (`ready`). Un boceto vuelve en
 * `pending`: la IA genera su prenda en segundo plano —y se cobra—, así que hay
 * que sondear con `fetchGarmentUploads` hasta `ready` o `failed`.
 */
export function uploadGarment(
  name: string,
  kind: GarmentKind,
  file: File,
  signal?: AbortSignal,
) {
  return api.postForm<GarmentUpload>('/garment-uploads', { file }, { name, kind }, { signal })
}

/**
 * Vuelve a pedirle a la IA la prenda de un boceto. Cada llamada se cobra.
 * Devuelve la prenda que se está generando: una nueva, o la misma si había
 * fallado.
 */
export function createGarmentVariant(id: number, signal?: AbortSignal) {
  return api.post<GarmentUpload>(`/garment-uploads/${id}/variants`, undefined, { signal })
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
    repeatAcross?: number
  },
  signal?: AbortSignal,
) {
  return api.post<Trial>(
    '/trials',
    {
      garment_upload_id: input.garmentUploadId,
      fabric_id: input.fabricId,
      repeat_across: input.repeatAcross,
    },
    { signal },
  )
}

/**
 * Repite una prueba con el motor de hoy: crea OTRA, con la misma prenda, tela y
 * repetición, y la antigua se conserva. Responde 202 en `pending`, como
 * `createTrial`. Nunca usa IA, aunque la antigua la usara.
 */
export function repeatTrial(id: number, signal?: AbortSignal) {
  return api.post<Trial>(`/trials/${id}/repeat`, undefined, { signal })
}

export function deleteTrial(id: number, signal?: AbortSignal) {
  return api.delete<{ message: string }>(`/trials/${id}`, { signal })
}

// --- Probador: fotos de persona y pruebas sobre ellas -----------------------

export function fetchPersonPhotos(signal?: AbortSignal) {
  return api.get<PersonPhoto[]>('/person-photos', { signal })
}

/** Se guarda enderezada y sin metadatos: ni la ubicación ni el teléfono. */
export function uploadPersonPhoto(file: File, signal?: AbortSignal) {
  return api.postForm<PersonPhoto>('/person-photos', { file }, {}, { signal })
}

/** Borra la foto y todas las pruebas hechas con ella. */
export function deletePersonPhoto(id: number, signal?: AbortSignal) {
  return api.delete<{ message: string }>(`/person-photos/${id}`, { signal })
}

export function fetchTryOns(signal?: AbortSignal) {
  return api.get<TryOn[]>('/try-ons', { signal })
}

/**
 * Le pone a la persona una prenda del taller. Responde 202 en `pending`: hay
 * que sondear con `fetchTryOns` hasta `completed` o `failed`.
 */
export function createTryOn(
  input: {
    personPhotoId: number
    fabricTrialId?: number
    garmentUploadId?: number
    category: GarmentCategory
  },
  signal?: AbortSignal,
) {
  return api.post<TryOn>(
    '/try-ons',
    {
      person_photo_id: input.personPhotoId,
      fabric_trial_id: input.fabricTrialId,
      garment_upload_id: input.garmentUploadId,
      category: input.category,
    },
    { signal },
  )
}

export function deleteTryOn(id: number, signal?: AbortSignal) {
  return api.delete<{ message: string }>(`/try-ons/${id}`, { signal })
}

// --- Autenticación ----------------------------------------------------------

export function login(email: string, password: string) {
  return api.post<TokenResponse>('/auth/login', { email, password })
}

export function register(name: string, email: string, password: string) {
  return api.post<User>('/users', { name, email, password })
}

/** Borra la cookie de sesión. La borra el servidor: un script no puede. */
export function logout() {
  return api.post<void>('/auth/logout', undefined)
}

/** Quién soy, según la cookie de sesión. Restaura la sesión al cargar. */
export function fetchCurrentUser(signal?: AbortSignal) {
  return api.get<User>('/auth/me', { signal })
}

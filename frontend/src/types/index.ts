/**
 * Tipos que reflejan el contrato de la API (los schemas Pydantic del backend).
 *
 * Se mantienen a mano por ahora. Si el contrato crece, se generarán a partir
 * del OpenAPI que ya publica FastAPI en /openapi.json.
 *
 * DOS PRODUCTOS EN UN MISMO CONTRATO
 * ----------------------------------
 * `Fabric`, `GarmentUpload` y `Trial` son el probador de telas: el producto
 * que describe el Product Vision Board. `Garment` es el catálogo del probador
 * con cámara, que es la funcionalidad adicional. No se mezclan.
 */

export type HealthStatus = 'ok' | 'degraded'

export interface Health {
  status: HealthStatus
  service: string
  version: string
  environment: string
  database: 'up' | 'down'
}

export interface User {
  id: number
  name: string
  email: string
  is_active: boolean
  created_at: string
  updated_at: string
}

/** Respuesta de POST /api/auth/login. */
export interface TokenResponse {
  access_token: string
  token_type: string
  /** Segundos de validez del token. */
  expires_in: number
}

// --- Catálogo de telas: el producto principal -------------------------------

export type FabricPattern = 'solid' | 'stripes' | 'checks' | 'print' | 'textured'

export interface Fabric {
  id: number
  name: string
  reference: string | null
  description: string | null

  composition: string | null
  /** Gramaje. Distingue una gasa de una lona mejor que cualquier adjetivo. */
  weight_gsm: number | null
  /** Ancho del rollo. Decide si salen las piezas del patrón. */
  width_cm: number | null
  price_per_meter: number | null
  currency: string

  color_name: string | null
  color_hex: string | null
  pattern: FabricPattern

  /** Foto de catálogo, para la ficha. */
  photo_url: string | null
  /** Mosaico que se estampa. Sin él, la tela no se puede probar. */
  texture_url: string | null
  default_repeat: number
  active: boolean

  created_at: string
  updated_at: string
}

export const FABRIC_PATTERN_LABELS: Record<FabricPattern, string> = {
  solid: 'Liso',
  stripes: 'Rayas',
  checks: 'Cuadros',
  print: 'Estampado',
  textured: 'Texturado',
}

// --- Prendas que sube el usuario --------------------------------------------

export type GarmentKind = 'photo' | 'sketch'

export interface GarmentUpload {
  id: number
  user_id: number
  name: string
  kind: GarmentKind

  image_url: string | null
  /** El recorte. Verlo es la única forma de entender una prueba mal salida. */
  mask_url: string | null
  mask_coverage: number | null
  width: number | null
  height: number | null

  /** Nulo si el recorte está bien. Si no, dice qué hacer. */
  mask_warning: string | null

  created_at: string
  updated_at: string
}

export const GARMENT_KIND_LABELS: Record<GarmentKind, string> = {
  photo: 'Fotografía',
  sketch: 'Boceto',
}

// --- Pruebas de tela --------------------------------------------------------

export type TrialStatus = 'pending' | 'processing' | 'completed' | 'failed'

/**
 * Con qué motor se generó.
 *
 * `retexture` reutiliza la luz de la fotografía —y en un boceto rellena el
 * dibujo conservando el trazo—: gratis, instantáneo y determinista. `ai` dibuja
 * la imagen entera: cuesta dinero, tarda, y reinterpreta el diseño. Se pide a
 * conciencia, nunca por defecto.
 */
export type TrialMethod = 'retexture' | 'ai'

export interface Trial {
  id: number
  user_id: number
  garment_upload_id: number
  fabric_id: number

  status: TrialStatus
  method: TrialMethod
  repeat_across: number

  output_image_url: string | null
  error_message: string | null
  provider: string | null

  /** Nulo en el motor determinista, que no cuesta nada. */
  tokens_used: number | null
  duration_ms: number | null
  notice: string | null

  created_at: string
  updated_at: string
}

export const TRIAL_METHOD_LABELS: Record<TrialMethod, string> = {
  retexture: 'Retexturizado',
  ai: 'IA generativa',
}

// --- Probador: la persona con la prenda puesta -----------------------------

/** Qué parte del cuerpo cubre la prenda: decide qué ropa de la foto se cambia. */
export type GarmentCategory = 'top' | 'bottom' | 'full'

export const CATEGORY_LABELS: Record<GarmentCategory, string> = {
  top: 'Parte de arriba',
  bottom: 'Parte de abajo',
  full: 'Vestido o mono',
}

export interface PersonPhoto {
  id: number
  user_id: number
  image_url: string | null
  width: number
  height: number
  created_at: string
  updated_at: string
}

export interface TryOn {
  id: number
  user_id: number
  person_photo_id: number
  /** La prenda sale de una prueba de tela (su imagen ya generada)… */
  fabric_trial_id: number | null
  /** …o de una prenda subida. */
  garment_upload_id: number | null
  category: GarmentCategory
  status: TrialStatus

  person_image_url: string | null
  /** La prenda exacta que se le mandó al modelo. */
  garment_image_url: string | null
  output_image_url: string | null

  error_message: string | null
  notice: string | null
  provider: string | null
  duration_ms: number | null
  /** Qué parte de la foto viene del modelo. El resto es la foto original. */
  edited_fraction: number | null

  created_at: string
  updated_at: string
}

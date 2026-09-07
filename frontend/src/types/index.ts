/**
 * Tipos que reflejan el contrato de la API (los schemas Pydantic del backend).
 *
 * Se mantienen a mano por ahora. Si el contrato crece, se generarán a partir
 * del OpenAPI que ya publica FastAPI en /openapi.json.
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

export type GarmentCategory = 'dress' | 'top' | 'bottom' | 'outerwear' | 'other'

export interface Garment {
  id: number
  name: string
  description: string | null
  category: GarmentCategory
  active: boolean
  image_url: string | null
  created_at: string
  updated_at: string
}

export type TryOnStatus = 'pending' | 'processing' | 'completed' | 'failed'

export interface TryOnSession {
  id: number
  user_id: number
  /** Uno de los dos, nunca ambos: la prueba parte del catalogo o de un diseno propio. */
  garment_id: number | null
  design_id: number | null
  status: TryOnStatus
  input_image_url: string | null
  output_image_url: string | null
  error_message: string | null
  provider: string | null
  created_at: string
  updated_at: string
}

// --- Fase 2: disenos generados por texto ---

export type DesignStatus = 'pending' | 'processing' | 'completed' | 'failed'

export interface Design {
  id: number
  user_id: number
  prompt: string
  /** Instruccion de la iteracion. Nulo en el primer diseno de una cadena. */
  refinement: string | null
  parent_id: number | null
  status: DesignStatus
  image_url: string | null
  error_message: string | null
  provider: string | null
  created_at: string
  updated_at: string
}

// --- Fase 3: perfil corporal y talla ---

export type MeasurementSource = 'manual' | 'analysis'

export interface BodyProfile {
  user_id: number
  height_cm: number | null
  weight_kg: number | null
  chest_cm: number | null
  waist_cm: number | null
  hips_cm: number | null
  inseam_cm: number | null
  source: MeasurementSource
  photo_url: string | null
  /** Solo llega tras un analisis. Sirve para avisar de que son estimaciones. */
  analysis_confidence: number | null
  created_at: string
  updated_at: string
}

/** Medidas editables del perfil. Todas opcionales: se envia solo lo que cambia. */
export type BodyMeasurements = Partial<
  Pick<BodyProfile, 'height_cm' | 'weight_kg' | 'chest_cm' | 'waist_cm' | 'hips_cm' | 'inseam_cm'>
>

export interface SizeRecommendation {
  /** Nulo cuando faltan medidas. `reason` explica cuales. */
  size: string | null
  category: GarmentCategory
  based_on: string[]
  reason: string
  per_measurement: Record<string, string>
  confidence: number
}

export const MEASUREMENT_LABELS: Record<string, string> = {
  height_cm: 'Altura',
  weight_kg: 'Peso',
  chest_cm: 'Pecho',
  waist_cm: 'Cintura',
  hips_cm: 'Cadera',
  inseam_cm: 'Entrepierna',
}

export const MEASUREMENT_UNITS: Record<string, string> = {
  height_cm: 'cm',
  weight_kg: 'kg',
  chest_cm: 'cm',
  waist_cm: 'cm',
  hips_cm: 'cm',
  inseam_cm: 'cm',
}

export const CATEGORY_LABELS: Record<GarmentCategory, string> = {
  dress: 'Vestidos',
  top: 'Superior',
  bottom: 'Inferior',
  outerwear: 'Abrigos',
  other: 'Otros',
}

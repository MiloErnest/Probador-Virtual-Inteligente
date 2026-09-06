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
  garment_id: number
  status: TryOnStatus
  input_image_url: string | null
  output_image_url: string | null
  error_message: string | null
  provider: string | null
  created_at: string
  updated_at: string
}

export const CATEGORY_LABELS: Record<GarmentCategory, string> = {
  dress: 'Vestidos',
  top: 'Superior',
  bottom: 'Inferior',
  outerwear: 'Abrigos',
  other: 'Otros',
}

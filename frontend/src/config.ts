/**
 * Configuración del cliente.
 *
 * Los valores llegan de variables de entorno con prefijo VITE_ (ver .env).
 * Recuerda: todo lo que se defina aquí acaba visible en el bundle público.
 */

export const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'
).replace(/\/$/, '')

export const API_PREFIX = '/api'

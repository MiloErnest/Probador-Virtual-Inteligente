/**
 * Cliente HTTP único de la aplicación.
 *
 * Se usa `fetch` nativo en lugar de axios: no aporta nada que necesitemos hoy
 * y es una dependencia menos que mantener.
 *
 * Ninguna página llama a `fetch` directamente; todas pasan por aquí, de modo
 * que la URL base, el manejo de errores y (más adelante) la cabecera de
 * autenticación se configuran en un solo sitio.
 */

import { API_BASE_URL, API_PREFIX } from '@/config'

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

function buildUrl(path: string, params?: Record<string, string | number | boolean | undefined>) {
  const url = new URL(`${API_BASE_URL}${API_PREFIX}${path}`)
  if (params) {
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined) url.searchParams.set(key, String(value))
    }
  }
  return url.toString()
}

async function parseError(response: Response): Promise<ApiError> {
  let message = `Error ${response.status}`
  try {
    const body = await response.json()
    // FastAPI devuelve el motivo en `detail` (string o lista de errores de validación).
    if (typeof body?.detail === 'string') {
      message = body.detail
    } else if (Array.isArray(body?.detail) && body.detail.length > 0) {
      message = body.detail.map((e: { msg?: string }) => e.msg ?? '').join('. ')
    }
  } catch {
    // Respuesta sin cuerpo JSON: se conserva el mensaje genérico.
  }
  return new ApiError(response.status, message)
}

async function request<T>(path: string, init: RequestInit, params?: Parameters<typeof buildUrl>[1]): Promise<T> {
  let response: Response
  try {
    response = await fetch(buildUrl(path, params), init)
  } catch (cause) {
    if (cause instanceof DOMException && cause.name === 'AbortError') throw cause
    // fetch solo rechaza por fallo de red, no por códigos 4xx/5xx.
    throw new ApiError(0, 'No se pudo contactar con el servidor. ¿Está arrancado el backend?')
  }

  if (!response.ok) throw await parseError(response)
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

export const api = {
  get<T>(path: string, options: { params?: Parameters<typeof buildUrl>[1]; signal?: AbortSignal } = {}) {
    return request<T>(path, { method: 'GET', signal: options.signal }, options.params)
  },

  post<T>(path: string, body: unknown, options: { signal?: AbortSignal } = {}) {
    return request<T>(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: options.signal,
    })
  },

  postFile<T>(path: string, file: File, options: { signal?: AbortSignal } = {}) {
    const formData = new FormData()
    formData.append('file', file)
    // Sin Content-Type manual: el navegador debe añadir el boundary de multipart.
    return request<T>(path, { method: 'POST', body: formData, signal: options.signal })
  },
}

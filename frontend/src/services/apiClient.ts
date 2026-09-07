/**
 * Cliente HTTP único de la aplicación.
 *
 * Se usa `fetch` nativo en lugar de axios: no aporta nada que necesitemos hoy
 * y es una dependencia menos que mantener.
 *
 * Ninguna página llama a `fetch` directamente; todas pasan por aquí, de modo
 * que la URL base, el manejo de errores y la cabecera de autenticación se
 * configuran en un solo sitio.
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

/**
 * Token de la sesión activa.
 *
 * Vive en una variable de módulo, no en el estado de React: `request()` es una
 * función suelta a la que no se le pueden pasar hooks. `AuthContext` es el
 * único que la escribe, mediante `setAuthToken`.
 */
let authToken: string | null = null

/** Se llama al iniciar sesión, al restaurarla y al cerrarla (con null). */
export function setAuthToken(token: string | null) {
  authToken = token
}

/**
 * Aviso de que el servidor ha rechazado el token.
 *
 * Sin esto, un token caducado dejaría la interfaz mostrando "sesión iniciada"
 * mientras todas las peticiones fallan. `AuthContext` registra aquí su
 * función de cierre de sesión.
 */
let onUnauthorized: (() => void) | null = null

export function setUnauthorizedHandler(handler: (() => void) | null) {
  onUnauthorized = handler
}

function authHeaders(): Record<string, string> {
  return authToken ? { Authorization: `Bearer ${authToken}` } : {}
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

  if (response.status === 401) {
    // El token no sirve: caducado, revocado o de una clave anterior. Se
    // cierra la sesión aquí, en el único punto por el que pasan todas las
    // peticiones, en lugar de que cada página lo detecte por su cuenta.
    onUnauthorized?.()
  }

  if (!response.ok) throw await parseError(response)
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

export const api = {
  get<T>(path: string, options: { params?: Parameters<typeof buildUrl>[1]; signal?: AbortSignal } = {}) {
    return request<T>(path, { method: 'GET', headers: authHeaders(), signal: options.signal }, options.params)
  },

  post<T>(path: string, body: unknown, options: { signal?: AbortSignal } = {}) {
    return request<T>(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify(body),
      signal: options.signal,
    })
  },

  /**
   * Envía un formulario multipart: uno o varios archivos y campos sueltos.
   *
   * `fields` existe porque una petición no puede llevar JSON y un archivo a la
   * vez: cuando hay archivo, TODO viaja como campos del formulario. Por eso
   * `garment_id` se manda así y no en un cuerpo JSON.
   */
  put<T>(path: string, body: unknown, options: { signal?: AbortSignal } = {}) {
    return request<T>(path, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify(body),
      signal: options.signal,
    })
  },

  delete<T>(path: string, options: { signal?: AbortSignal } = {}) {
    return request<T>(path, { method: 'DELETE', headers: authHeaders(), signal: options.signal })
  },

  postForm<T>(
    path: string,
    files: Record<string, File>,
    fields: Record<string, string | number> = {},
    options: { signal?: AbortSignal } = {},
  ) {
    const formData = new FormData()
    for (const [name, file] of Object.entries(files)) formData.append(name, file)
    for (const [name, value] of Object.entries(fields)) formData.append(name, String(value))
    // Sin Content-Type manual: el navegador debe añadir el boundary de multipart.
    return request<T>(path, { method: 'POST', headers: authHeaders(), body: formData, signal: options.signal })
  },
}

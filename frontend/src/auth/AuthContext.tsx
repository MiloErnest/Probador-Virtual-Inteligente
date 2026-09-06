/**
 * Sesión del usuario.
 *
 * Único dueño del token en el frontend. Nadie más lo lee ni lo escribe: las
 * páginas preguntan por `user`, y el cliente HTTP recibe el token por
 * `setAuthToken`.
 *
 * DÓNDE SE GUARDA EL TOKEN
 * ------------------------
 * En `localStorage`, para que recargar la página no cierre la sesión.
 *
 * Riesgo asumido y documentado: un fallo de XSS permitiría leerlo, cosa que
 * no ocurriría con una cookie `httpOnly`. La alternativa segura exige manejar
 * CSRF y cookies entre orígenes distintos (5173 -> 8000), que es bastante más
 * maquinaria de la que este proyecto necesita hoy. Si algún día se despliega
 * de cara al público, este es el primer punto a revisar.
 *
 * QUÉ PASA AL RECARGAR
 * --------------------
 * El token guardado no se cree sin más: se valida contra `GET /api/auth/me`.
 * Confiar en él sin comprobarlo pintaría la interfaz como "sesión iniciada"
 * aunque estuviera caducado, y el usuario se encontraría errores por todas
 * partes sin entender por qué.
 */

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'

import { setAuthToken, setUnauthorizedHandler } from '@/services/apiClient'
import * as endpoints from '@/services/endpoints'
import type { User } from '@/types'

const TOKEN_STORAGE_KEY = 'vfit.access_token'

interface AuthContextValue {
  user: User | null
  /** true mientras se comprueba el token guardado al arrancar. */
  initialising: boolean
  isAuthenticated: boolean
  login: (email: string, password: string) => Promise<void>
  register: (name: string, email: string, password: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

function readStoredToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_STORAGE_KEY)
  } catch {
    // Navegación privada o almacenamiento bloqueado: se sigue sin sesión
    // persistente en lugar de romper la aplicación entera.
    return null
  }
}

function writeStoredToken(token: string | null) {
  try {
    if (token === null) localStorage.removeItem(TOKEN_STORAGE_KEY)
    else localStorage.setItem(TOKEN_STORAGE_KEY, token)
  } catch {
    // Igual que arriba: la sesión funcionará hasta cerrar la pestaña.
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [initialising, setInitialising] = useState(true)

  const logout = useCallback(() => {
    setAuthToken(null)
    writeStoredToken(null)
    setUser(null)
  }, [])

  // Un 401 en cualquier petición cierra la sesión. Lo registra el contexto
  // porque es quien sabe cómo hacerlo; el cliente HTTP solo avisa.
  useEffect(() => {
    setUnauthorizedHandler(logout)
    return () => setUnauthorizedHandler(null)
  }, [logout])

  // Al arrancar: si hay token guardado, se valida contra el backend.
  useEffect(() => {
    const token = readStoredToken()
    if (token === null) {
      setInitialising(false)
      return
    }

    setAuthToken(token)

    const controller = new AbortController()
    let active = true

    endpoints
      .fetchCurrentUser(controller.signal)
      .then((currentUser) => {
        if (active) setUser(currentUser)
      })
      .catch(() => {
        // Token caducado o backend caído. En ambos casos se empieza sin
        // sesión; si el backend está caído, el usuario verá el indicador de
        // estado en rojo y podrá volver a entrar cuando vuelva.
        if (active) logout()
      })
      .finally(() => {
        if (active) setInitialising(false)
      })

    return () => {
      active = false
      controller.abort()
    }
  }, [logout])

  const doLogin = useCallback(async (email: string, password: string) => {
    const { access_token } = await endpoints.login(email, password)

    // El token se activa ANTES de pedir /auth/me: esa petición ya necesita ir
    // firmada.
    setAuthToken(access_token)
    try {
      const currentUser = await endpoints.fetchCurrentUser()
      writeStoredToken(access_token)
      setUser(currentUser)
    } catch (error) {
      // Si /auth/me falla justo después de un login correcto, no se guarda
      // nada: es preferible quedarse sin sesión que con una a medias.
      setAuthToken(null)
      throw error
    }
  }, [])

  const doRegister = useCallback(
    async (name: string, email: string, password: string) => {
      await endpoints.register(name, email, password)
      // Registrarse e iniciar sesión a continuación evita pedir dos veces la
      // misma contraseña que el usuario acaba de escribir.
      await doLogin(email, password)
    },
    [doLogin],
  )

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      initialising,
      isAuthenticated: user !== null,
      login: doLogin,
      register: doRegister,
      logout,
    }),
    [user, initialising, doLogin, doRegister, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext)
  if (context === null) {
    throw new Error('useAuth debe usarse dentro de <AuthProvider>.')
  }
  return context
}

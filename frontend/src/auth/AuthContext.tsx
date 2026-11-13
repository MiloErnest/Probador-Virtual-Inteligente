/**
 * Sesión del usuario.
 *
 * Las páginas preguntan por `user`; nadie más sabe cómo se lleva la sesión.
 *
 * DÓNDE ESTÁ LA SESIÓN (Ep5-Hu6)
 * ------------------------------
 * En una cookie `httpOnly` que pone el servidor al iniciar sesión. El frontend
 * NO guarda el token: ni en `localStorage`, que era donde estaba hasta el
 * 12/11/2026 y donde un fallo de XSS se lo llevaba, ni en memoria. El
 * navegador manda la cookie solo, y ningún script la puede leer.
 *
 * Cerrar sesión pide al servidor que la borre: un script no puede borrar una
 * cookie `httpOnly`.
 *
 * QUÉ PASA AL RECARGAR
 * --------------------
 * Se pregunta `GET /api/auth/me`: si la cookie sigue valiendo, ahí está el
 * usuario; si no, un 401 y se empieza sin sesión. Pintar «sesión iniciada»
 * sin comprobarlo dejaría al usuario frente a errores sin entender por qué.
 */

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'

import { setUnauthorizedHandler } from '@/services/apiClient'
import * as endpoints from '@/services/endpoints'
import type { User } from '@/types'

/** Donde estaba el token antes del 12/11/2026. Se borra si queda alguno. */
const TOKEN_ANTIGUO = 'vfit.access_token'

interface AuthContextValue {
  user: User | null
  /** true mientras se comprueba la sesión al arrancar. */
  initialising: boolean
  isAuthenticated: boolean
  login: (email: string, password: string) => Promise<void>
  register: (name: string, email: string, password: string) => Promise<void>
  logout: () => void
  /** Vuelve a preguntar quién soy: tras verificar el correo, por ejemplo. */
  refreshUser: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

function borrarTokenAntiguo() {
  try {
    localStorage.removeItem(TOKEN_ANTIGUO)
  } catch {
    // Almacenamiento bloqueado: no había nada que borrar.
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [initialising, setInitialising] = useState(true)

  // Lo que pasa en la pantalla al perder la sesión, sin llamar al servidor:
  // es lo que hace un 401, cuando la cookie ya no vale.
  const olvidar = useCallback(() => setUser(null), [])

  const logout = useCallback(() => {
    setUser(null)
    // Si falla (servidor caído), la cookie caduca sola; la pantalla ya está
    // sin sesión.
    endpoints.logout().catch(() => undefined)
  }, [])

  // Un 401 en cualquier petición deja la interfaz sin sesión. Lo registra el
  // contexto porque es quien sabe cómo hacerlo; el cliente HTTP solo avisa.
  useEffect(() => {
    setUnauthorizedHandler(olvidar)
    return () => setUnauthorizedHandler(null)
  }, [olvidar])

  // Al arrancar: ¿hay sesión? Lo dice el servidor, que es quien ve la cookie.
  useEffect(() => {
    borrarTokenAntiguo()

    const controller = new AbortController()
    let active = true

    endpoints
      .fetchCurrentUser(controller.signal)
      .then((currentUser) => {
        if (active) setUser(currentUser)
      })
      .catch(() => {
        // Sin sesión, caducada o backend caído: se empieza sin sesión. Si el
        // backend está caído, el indicador de estado lo dice.
        if (active) setUser(null)
      })
      .finally(() => {
        if (active) setInitialising(false)
      })

    return () => {
      active = false
      controller.abort()
    }
  }, [])

  const doLogin = useCallback(async (email: string, password: string) => {
    // El servidor deja la cookie; el token del cuerpo no se guarda.
    await endpoints.login(email, password)
    setUser(await endpoints.fetchCurrentUser())
  }, [])

  const refreshUser = useCallback(async () => {
    try {
      setUser(await endpoints.fetchCurrentUser())
    } catch {
      // Sin sesión en este navegador: no hay nada que refrescar.
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
      refreshUser,
    }),
    [user, initialising, doLogin, doRegister, logout, refreshUser],
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

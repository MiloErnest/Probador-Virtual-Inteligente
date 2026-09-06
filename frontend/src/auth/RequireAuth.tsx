/**
 * Envoltorio de rutas que exigen sesión iniciada.
 *
 * No sustituye a la protección del backend, la acompaña: aquí solo se evita
 * enseñar una pantalla que va a fallar. Quien decide de verdad es la API.
 */

import { Navigate, Outlet, useLocation } from 'react-router-dom'

import { useAuth } from '@/auth/AuthContext'
import { LoadingBlock } from '@/components/StateBlocks'

export default function RequireAuth() {
  const { isAuthenticated, initialising } = useAuth()
  const location = useLocation()

  // Mientras se valida el token guardado no se sabe aún si hay sesión.
  // Redirigir ahora echaría a la calle a quien sí la tiene, cada vez que
  // recarga la página.
  if (initialising) {
    return <LoadingBlock label="Comprobando la sesión…" />
  }

  if (!isAuthenticated) {
    // `state.from` permite volver a donde iba después de identificarse, en
    // lugar de dejarlo en la portada.
    return <Navigate to="/entrar" replace state={{ from: location.pathname }} />
  }

  return <Outlet />
}

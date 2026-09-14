import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'

import { useAuth } from '@/auth/AuthContext'
import AuthLayout from '@/components/AuthLayout'
import { ErrorBlock } from '@/components/StateBlocks'

export default function LoginPage() {
  const { login, isAuthenticated, initialising } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [enviando, setEnviando] = useState(false)

  // A dónde volver tras identificarse: la página que intentaba abrirse, o el
  // probador, que es a lo que se viene.
  const destino = (location.state as { from?: string } | null)?.from ?? '/probador'

  if (!initialising && isAuthenticated) {
    return <Navigate to={destino} replace />
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    setEnviando(true)
    try {
      await login(email, password)
      navigate(destino, { replace: true })
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'No se pudo iniciar sesión.')
    } finally {
      setEnviando(false)
    }
  }

  return (
    <AuthLayout
      titulo="Entrar"
      lema="Tu cuenta solo guarda quién eres. Ni una foto, ni una medida, ni lo que te has probado."
    >
      <h1 className="font-display text-titulo">Entrar</h1>
      <p className="mt-2 text-sm text-ink-60">Para abrir el probador con la cámara.</p>

      {error && (
        <div className="mt-6">
          <ErrorBlock title="No se pudo iniciar sesión" detail={error} />
        </div>
      )}

      <form onSubmit={handleSubmit} className="mt-8 space-y-5" noValidate>
        <div className="space-y-1.5">
          <label htmlFor="email" className="block text-sm font-medium">
            Correo electrónico
          </label>
          <input
            id="email"
            type="email"
            required
            autoComplete="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            className="campo"
          />
        </div>

        <div className="space-y-1.5">
          <label htmlFor="password" className="block text-sm font-medium">
            Contraseña
          </label>
          <input
            id="password"
            type="password"
            required
            autoComplete="current-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            className="campo"
          />
        </div>

        <button type="submit" className="btn-primary w-full" disabled={enviando}>
          {enviando ? 'Entrando…' : 'Entrar'}
        </button>
      </form>

      <p className="mt-6 text-sm text-ink-60">
        ¿Todavía no tienes cuenta?{' '}
        <Link to="/registro" className="enlace font-medium text-ink">
          Crear una
        </Link>
      </p>
    </AuthLayout>
  )
}

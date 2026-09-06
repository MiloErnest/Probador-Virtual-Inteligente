import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'

import { useAuth } from '@/auth/AuthContext'
import { ErrorBlock } from '@/components/StateBlocks'

export default function LoginPage() {
  const { login, isAuthenticated, initialising } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  // A donde volver tras identificarse: la pagina que intentaba abrirse, o
  // "Mis pruebas" si se llego aqui directamente.
  const destination = (location.state as { from?: string } | null)?.from ?? '/mis-pruebas'

  if (!initialising && isAuthenticated) {
    return <Navigate to={destination} replace />
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      await login(email, password)
      navigate(destination, { replace: true })
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'No se pudo iniciar sesion.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="mx-auto max-w-md space-y-8">
      <header>
        <h1 className="font-display text-3xl">Entrar</h1>
        <p className="mt-1.5 text-sm text-ink-muted">
          Accede para ver tu historial de pruebas.
        </p>
      </header>

      {error && <ErrorBlock title="No se pudo iniciar sesion" detail={error} />}

      <form onSubmit={handleSubmit} className="card space-y-5 p-6" noValidate>
        <div className="space-y-1.5">
          <label htmlFor="email" className="block text-sm font-medium">
            Correo electronico
          </label>
          <input
            id="email"
            type="email"
            required
            autoComplete="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            className="w-full rounded-lg border border-black/10 bg-white px-3.5 py-2.5 text-sm"
          />
        </div>

        <div className="space-y-1.5">
          <label htmlFor="password" className="block text-sm font-medium">
            Contrasena
          </label>
          <input
            id="password"
            type="password"
            required
            autoComplete="current-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            className="w-full rounded-lg border border-black/10 bg-white px-3.5 py-2.5 text-sm"
          />
        </div>

        <button type="submit" className="btn-primary w-full" disabled={submitting}>
          {submitting ? 'Entrando…' : 'Entrar'}
        </button>
      </form>

      <p className="text-center text-sm text-ink-muted">
        ¿Todavia no tienes cuenta?{' '}
        <Link to="/registro" className="font-medium text-ink underline underline-offset-4">
          Crear una
        </Link>
      </p>
    </div>
  )
}

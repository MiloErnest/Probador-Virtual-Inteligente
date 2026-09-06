import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'

import { useAuth } from '@/auth/AuthContext'
import { ErrorBlock } from '@/components/StateBlocks'

// Los mismos limites que valida el backend (app/schemas/user.py). Se repiten
// aqui para avisar antes de enviar, no para sustituir esa validacion.
const MIN_PASSWORD = 8
const MAX_PASSWORD = 72

export default function RegisterPage() {
  const { register, isAuthenticated, initialising } = useAuth()
  const navigate = useNavigate()

  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  if (!initialising && isAuthenticated) {
    return <Navigate to="/mis-pruebas" replace />
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      await register(name, email, password)
      navigate('/mis-pruebas', { replace: true })
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'No se pudo crear la cuenta.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="mx-auto max-w-md space-y-8">
      <header>
        <h1 className="font-display text-3xl">Crear cuenta</h1>
        <p className="mt-1.5 text-sm text-ink-muted">
          Necesaria para guardar tus pruebas virtuales.
        </p>
      </header>

      {error && <ErrorBlock title="No se pudo crear la cuenta" detail={error} />}

      <form onSubmit={handleSubmit} className="card space-y-5 p-6" noValidate>
        <div className="space-y-1.5">
          <label htmlFor="name" className="block text-sm font-medium">
            Nombre
          </label>
          <input
            id="name"
            type="text"
            required
            maxLength={120}
            autoComplete="name"
            value={name}
            onChange={(event) => setName(event.target.value)}
            className="w-full rounded-lg border border-black/10 bg-white px-3.5 py-2.5 text-sm"
          />
        </div>

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
            minLength={MIN_PASSWORD}
            maxLength={MAX_PASSWORD}
            autoComplete="new-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            className="w-full rounded-lg border border-black/10 bg-white px-3.5 py-2.5 text-sm"
          />
          <p className="text-xs text-ink-muted">
            Entre {MIN_PASSWORD} y {MAX_PASSWORD} caracteres.
          </p>
        </div>

        <button type="submit" className="btn-primary w-full" disabled={submitting}>
          {submitting ? 'Creando…' : 'Crear cuenta'}
        </button>
      </form>

      <p className="text-center text-sm text-ink-muted">
        ¿Ya tienes cuenta?{' '}
        <Link to="/entrar" className="font-medium text-ink underline underline-offset-4">
          Entrar
        </Link>
      </p>
    </div>
  )
}

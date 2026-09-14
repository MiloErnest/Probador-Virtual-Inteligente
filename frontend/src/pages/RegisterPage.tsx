import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'

import { useAuth } from '@/auth/AuthContext'
import AuthLayout from '@/components/AuthLayout'
import { ErrorBlock } from '@/components/StateBlocks'

// Los mismos límites que valida el backend (app/schemas/user.py). Se repiten
// aquí para avisar antes de enviar, no para sustituir esa validación.
const MIN_PASSWORD = 8
const MAX_PASSWORD = 72

export default function RegisterPage() {
  const { register, isAuthenticated, initialising } = useAuth()
  const navigate = useNavigate()

  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [enviando, setEnviando] = useState(false)

  if (!initialising && isAuthenticated) {
    return <Navigate to="/probador" replace />
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    setEnviando(true)
    try {
      await register(name, email, password)
      navigate('/probador', { replace: true })
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'No se pudo crear la cuenta.')
    } finally {
      setEnviando(false)
    }
  }

  return (
    <AuthLayout
      titulo="Crear cuenta"
      lema="Nombre, correo y contraseña. Nada más, porque nada más hace falta."
    >
      <h1 className="font-display text-titulo">Crear cuenta</h1>
      <p className="mt-2 text-sm text-ink-60">Se tarda menos que en encender la cámara.</p>

      {error && (
        <div className="mt-6">
          <ErrorBlock title="No se pudo crear la cuenta" detail={error} />
        </div>
      )}

      <form onSubmit={handleSubmit} className="mt-8 space-y-5" noValidate>
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
            className="campo"
          />
        </div>

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
            minLength={MIN_PASSWORD}
            maxLength={MAX_PASSWORD}
            autoComplete="new-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            className="campo"
          />
          <p className="text-xs text-ink-60">
            Entre {MIN_PASSWORD} y {MAX_PASSWORD} caracteres.
          </p>
        </div>

        <button type="submit" className="btn-primary w-full" disabled={enviando}>
          {enviando ? 'Creando…' : 'Crear cuenta'}
        </button>
      </form>

      <p className="mt-6 text-sm text-ink-60">
        ¿Ya tienes cuenta?{' '}
        <Link to="/entrar" className="enlace font-medium text-ink">
          Entrar
        </Link>
      </p>
    </AuthLayout>
  )
}

/**
 * Donde abre el enlace del correo de verificación (Ep5-Hu7).
 *
 * Pública: quien abre el enlace puede hacerlo desde el móvil, sin sesión. El
 * token ya dice qué cuenta es. Si hay sesión en este navegador, se refresca el
 * usuario para que la interfaz deje de pedir la verificación sin recargar.
 */

import { useEffect, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import { useAuth } from '@/auth/AuthContext'
import { ErrorBlock, LoadingBlock, Notice } from '@/components/StateBlocks'
import { verifyEmail } from '@/services/endpoints'

type Estado = { tipo: 'comprobando' } | { tipo: 'hecho'; email: string } | { tipo: 'fallo'; detalle: string }

export default function VerificarCorreoPage() {
  const [params] = useSearchParams()
  const { isAuthenticated, refreshUser } = useAuth()
  const [estado, setEstado] = useState<Estado>({ tipo: 'comprobando' })
  // En desarrollo, React monta dos veces: el enlace se manda una sola.
  const enviado = useRef(false)

  useEffect(() => {
    if (enviado.current) return
    enviado.current = true

    const token = params.get('token')
    if (!token) {
      setEstado({ tipo: 'fallo', detalle: 'Este enlace no trae nada que comprobar.' })
      return
    }
    verifyEmail(token)
      .then((usuario) => {
        setEstado({ tipo: 'hecho', email: usuario.email })
        return refreshUser()
      })
      .catch((causa: unknown) =>
        setEstado({
          tipo: 'fallo',
          detalle: causa instanceof Error ? causa.message : 'No se pudo comprobar el enlace.',
        }),
      )
  }, [params, refreshUser])

  return (
    <div className="wrap max-w-xl space-y-8">
      <header className="border-b border-ink-10 pb-6">
        <p className="rotulo">Tu cuenta</p>
        <h1 className="mt-3 font-display text-titulo">Confirmar el correo</h1>
      </header>

      {estado.tipo === 'comprobando' && <LoadingBlock label="Comprobando el enlace…" />}

      {estado.tipo === 'hecho' && (
        <Notice title="Correo confirmado">
          <p>
            {estado.email} ya está confirmado. Ya puedes generar prendas a partir de tus
            bocetos.
          </p>
          <p>
            <Link
              to={isAuthenticated ? '/bocetos' : '/entrar'}
              className="font-medium underline underline-offset-4"
            >
              {isAuthenticated ? 'Ir a Bocetos' : 'Entrar'}
            </Link>
          </p>
        </Notice>
      )}

      {estado.tipo === 'fallo' && (
        <ErrorBlock
          title="No se pudo confirmar"
          detail={estado.detalle}
          action={
            <Link to={isAuthenticated ? '/perfil' : '/entrar'} className="btn-ghost">
              {isAuthenticated ? 'Pedir otro enlace' : 'Entrar para pedir otro'}
            </Link>
          }
        />
      )}
    </div>
  )
}

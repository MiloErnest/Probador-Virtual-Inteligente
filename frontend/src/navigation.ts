/**
 * Mapa de navegación.
 *
 * Ya no hay secciones "de fases futuras" con aviso en lugar de contenido: la
 * aplicación hace una cosa —vestirte delante de la cámara— y todo lo que se
 * enseña funciona. Un menú lleno de enlaces que no llevan a nada no comunica
 * ambición, comunica que no está terminado.
 */

export interface NavItem {
  to: string
  label: string
  /** Requiere sesión iniciada. Se oculta a quien no ha entrado. */
  requiresAuth?: boolean
}

export const NAV_ITEMS: NavItem[] = [
  { to: '/', label: 'Inicio' },
  { to: '/catalogo', label: 'Catálogo' },
  { to: '/probador', label: 'Probador', requiresAuth: true },
  { to: '/perfil', label: 'Perfil', requiresAuth: true },
]

/**
 * Mapa de navegación.
 *
 * `phase` indica en qué fase del proyecto se activa cada sección. Las
 * secciones de fases futuras son navegables pero muestran un aviso en lugar
 * de un enlace muerto: así la estructura completa del producto queda visible
 * desde el primer día.
 */

export interface NavItem {
  to: string
  label: string
  /** Fase en la que la sección queda operativa. 1 = MVP actual. */
  phase: number
  ready: boolean
  /** Requiere sesión iniciada. Se oculta a quien no ha entrado. */
  requiresAuth?: boolean
}

export const NAV_ITEMS: NavItem[] = [
  { to: '/', label: 'Inicio', phase: 1, ready: true },
  { to: '/catalogo', label: 'Catálogo', phase: 1, ready: true },
  { to: '/probador', label: 'Probador virtual', phase: 1, ready: true, requiresAuth: true },
  { to: '/mis-pruebas', label: 'Mis pruebas', phase: 1, ready: true, requiresAuth: true },
  { to: '/disenar', label: 'Diseñar con IA', phase: 2, ready: true, requiresAuth: true },
  { to: '/cuerpo', label: 'Mi cuerpo', phase: 3, ready: true, requiresAuth: true },
  { to: '/perfil', label: 'Perfil', phase: 1, ready: true, requiresAuth: true },
]

/**
 * Mapa de navegación.
 *
 * El orden refleja el producto: primero las telas —el catálogo de la tienda,
 * que es el escaparate— y después el taller, que es donde el usuario trabaja.
 * El probador con cámara va al final porque es la funcionalidad adicional, no
 * el producto.
 */

export interface NavItem {
  to: string
  label: string
  /** Requiere sesión iniciada. Se oculta a quien no ha entrado. */
  requiresAuth?: boolean
}

export const NAV_ITEMS: NavItem[] = [
  { to: '/', label: 'Inicio' },
  { to: '/telas', label: 'Telas' },
  { to: '/taller', label: 'Mi taller', requiresAuth: true },
  { to: '/probador', label: 'Probador con cámara', requiresAuth: true },
  { to: '/perfil', label: 'Perfil', requiresAuth: true },
]

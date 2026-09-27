/**
 * Mapa de navegación.
 *
 * El orden refleja el producto: primero las telas —el catálogo de la tienda,
 * que es el escaparate—, después el taller, donde se prueban telas sobre una
 * prenda, y por último el probador, donde esa prenda se prueba sobre una
 * persona.
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
  { to: '/probador', label: 'Probador', requiresAuth: true },
  { to: '/perfil', label: 'Perfil', requiresAuth: true },
]

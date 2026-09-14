/**
 * Sistema visual: blanco y negro, sin color de acento.
 *
 * POR QUE NO HAY UNA PALETA DE COLOR
 * ----------------------------------
 * La version anterior tenia un violeta de acento sobre un fondo crema. El
 * resultado se veia apagado, y no por falta de color: el fondo crema (#FAF8F5)
 * y el texto gris (#4A4540) daban un contraste bajo en TODA la pagina, asi que
 * nada destacaba porque todo estaba a media luz.
 *
 * La solucion no es meter mas color, es usar los extremos. Blanco puro, negro
 * casi puro, y toda la escala intermedia reservada para bordes y texto
 * secundario. El contraste hace el trabajo que antes se le pedia al acento, y
 * ademas le va a una aplicacion de ropa: un catalogo se ve mejor sobre blanco.
 *
 * LOS GRISES SON OPACIDADES DE LA TINTA, NO COLORES NUEVOS
 * --------------------------------------------------------
 * `ink-50` es la misma tinta al 50%. Asi ningun gris se desvia hacia el azul o
 * el verde por accidente, que es lo que suele ensuciar una escala neutra.
 */

/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'Segoe UI', 'sans-serif'],
        display: ['"Playfair Display"', 'Georgia', 'serif'],
      },
      colors: {
        ink: {
          DEFAULT: '#0A0A0B',
          80: '#3A3A3D',
          60: '#66666B',
          40: '#94949A',
          20: '#C7C7CC',
          10: '#E4E4E7',
          5: '#F2F2F4',
        },
        paper: '#FFFFFF',
        /** Fondo de seccion. Apenas se separa del blanco, y esa es la idea. */
        bone: '#F7F7F5',
      },
      fontSize: {
        // Tipografia fluida: crece con la ventana en vez de dar saltos entre
        // puntos de ruptura. Un titular no deberia cambiar de tamano de golpe
        // al girar el movil.
        display: ['clamp(2.5rem, 7vw, 5rem)', { lineHeight: '0.98', letterSpacing: '-0.03em' }],
        titulo: ['clamp(1.75rem, 3.6vw, 2.75rem)', { lineHeight: '1.06', letterSpacing: '-0.02em' }],
        seccion: ['clamp(1.25rem, 2.2vw, 1.6rem)', { lineHeight: '1.15', letterSpacing: '-0.01em' }],
      },
      letterSpacing: {
        rotulo: '0.18em',
      },
      borderRadius: {
        DEFAULT: '4px',
        marco: '6px',
      },
      boxShadow: {
        // Una sola sombra en todo el sistema, y muy contenida: la jerarquia la
        // dan los bordes y el contraste, no las sombras.
        alza: '0 12px 32px -18px rgba(10, 10, 11, 0.45)',
      },
      keyframes: {
        entrar: {
          from: { opacity: '0', transform: 'translateY(8px)' },
          to: { opacity: '1', transform: 'none' },
        },
        latido: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.35' },
        },
      },
      animation: {
        entrar: 'entrar 0.4s cubic-bezier(0.16, 1, 0.3, 1) both',
        latido: 'latido 1.6s ease-in-out infinite',
      },
    },
  },
  plugins: [],
}

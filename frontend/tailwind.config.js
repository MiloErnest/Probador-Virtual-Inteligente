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
          DEFAULT: '#12100E',
          soft: '#4A4540',
          muted: '#8A827A',
        },
        canvas: '#FAF8F5',
        accent: {
          DEFAULT: '#7C3AED',
          soft: '#EDE7FE',
        },
      },
      borderRadius: {
        xl2: '1.25rem',
      },
    },
  },
  plugins: [],
}

/**
 * Prepara los archivos que MediaPipe necesita servir por HTTP.
 *
 * POR QUE HACE FALTA UN SCRIPT
 * ----------------------------
 * El runtime WASM de MediaPipe pesa unos 22 MB. Meterlo en git seria inflar el
 * repositorio con binarios que `npm install` ya descarga de todos modos, asi
 * que `public/mediapipe/` esta en .gitignore y se rellena desde node_modules.
 *
 * Se ejecuta solo, antes de `npm run dev` y de `npm run build`, y no necesita
 * conexion: los archivos ya estan en node_modules.
 *
 * El modelo de pose (`public/models/*.task`, 5,6 MB) SI se versiona: es un
 * archivo suelto que no viene con ningun paquete, y sin el la aplicacion no
 * arranca. Preferible 5,6 MB en git que un README que diga "y ahora
 * descargate esto a mano".
 */

import { cpSync, existsSync, mkdirSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const raiz = join(dirname(fileURLToPath(import.meta.url)), '..')
const origen = join(raiz, 'node_modules', '@mediapipe', 'tasks-vision', 'wasm')
const destino = join(raiz, 'public', 'mediapipe', 'wasm')

if (!existsSync(origen)) {
  console.error(
    'No se encuentra el WASM de MediaPipe en node_modules.\n' +
      'Ejecuta primero:  npm install',
  )
  process.exit(1)
}

mkdirSync(destino, { recursive: true })
cpSync(origen, destino, { recursive: true })
console.log('MediaPipe listo en public/mediapipe/wasm/')

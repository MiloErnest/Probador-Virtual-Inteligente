# Prendas de ejemplo

Fotografias de producto para probar el catalogo, el probador y el recorte de
fondo. Estan aqui, versionadas, para que quien clone el repositorio pueda
usar la aplicacion sin tener que buscar imagenes por su cuenta.

Se subieron con el script del proyecto; para volver a cargarlas:

    python -m scripts.seed --con-prendas-reales

Los nombres se normalizaron (sin mayusculas, sin espacios, sin comas) porque
un archivo llamado `Chaqueta de cuero Hombre, Negra.jpg` obliga a entrecomillar
en cada comando y da problemas al pasarlo por URL.

## Por que estan en `assets/` y no en `backend/storage/`

`backend/storage/` es el almacen en tiempo de ejecucion: lo que la aplicacion
escribe cuando alguien sube algo. Esta fuera de git a proposito, y su contenido
se puede borrar sin perder nada del proyecto.

Estas cinco imagenes son lo contrario: material de partida del repositorio, que
no debe desaparecer al vaciar el almacen.

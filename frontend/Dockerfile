# Imagen del frontend: se compila con Node y se sirve con Nginx.
#
# Aqui SI hace falta multi-stage. Node y node_modules pesan cientos de
# megabytes y no sirven para nada en ejecucion: lo unico que hay que servir
# son los archivos estaticos que produce `vite build`.

# --- Etapa 1: compilar ---
FROM node:24-alpine AS build

WORKDIR /app

# Primero las dependencias, para aprovechar la cache de capas de Docker.
# `npm ci` y no `npm install`: instala exactamente lo que fija el
# package-lock.json, sin resolver versiones de nuevo.
COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# La URL de la API se resuelve en tiempo de COMPILACION, no de ejecucion:
# Vite sustituye import.meta.env.VITE_* dentro del bundle. Por eso llega como
# argumento de build y no como variable de entorno del contenedor.
ARG VITE_API_BASE_URL=http://localhost:8000
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

RUN npm run build

# --- Etapa 2: servir ---
FROM nginx:1.27-alpine

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

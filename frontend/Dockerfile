# --- build: static bundle --------------------------------------------------
# Node 24: satisfies Vite 8 (^20.19 || >=22.12) and Vitest 5 (^22.12 || ^24 || >=26).
FROM node:24-slim AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# Baked into the JS at build time, and read by the *browser*, so it must be a
# URL reachable from the user's machine (e.g. http://localhost:8000), never a
# compose service name like http://backend:8000.
ARG VITE_API_URL=http://localhost:8000
ENV VITE_API_URL=$VITE_API_URL

# tsc -b (type-check) + vite build
RUN npm run build

# --- serve: nginx ----------------------------------------------------------
FROM nginx:1.30-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

FROM node:20-alpine AS build

WORKDIR /app

# Install dependencies first (layer cache — won't re-download unless package.json changes)
COPY package*.json ./
RUN npm ci

# Copy source and build
COPY . .
RUN npm run build

# --- Production: serve from nginx ---
FROM nginx:1.29.8-alpine-slim

# Copy built Angular files
COPY --from=build /app/dist/frontend/browser /usr/share/nginx/html

# Nginx config: serve Angular + proxy /api/ to backend
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
FROM node:20-alpine AS build

WORKDIR /app

# Install dependencies first (layer cache)
COPY package*.json ./
RUN npm ci

# Copy source and build
COPY . .
RUN npm run build

# --- Production: serve from nginx ---
FROM nginx:1.29.8-alpine-slim

# Copy built Angular files
COPY --from=build /app/dist/frontend/browser /usr/share/nginx/html

# Copy Nginx config as a template for envsubst
COPY nginx.conf /etc/nginx/conf.d/default.conf.template

EXPOSE 80

# Use envsubst to inject BACKEND_URL into the config at startup
CMD ["sh", "-c", "envsubst '$BACKEND_URL' < /etc/nginx/conf.d/default.conf.template > /etc/nginx/conf.d/default.conf && exec nginx -g 'daemon off;'"]
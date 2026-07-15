FROM node:24.18.0-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN test "$(node --version)" = "v24.18.0" \
    && test "$(npm --version)" = "11.16.0" \
    && npm ci --no-audit --no-fund --strict-allow-scripts
COPY . .
RUN npm run build

FROM nginxinc/nginx-unprivileged:1.30.3-alpine
COPY --from=build --chown=101:101 /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 8080

FROM mcr.microsoft.com/playwright:v1.61.1-noble AS build

WORKDIR /app

COPY package*.json ./
RUN test "$(node --version)" = "v24.18.0" \
    && test "$(npm --version)" = "11.16.0" \
    && npm ci --no-audit --no-fund --strict-allow-scripts

COPY tsconfig.json ./
COPY src ./src
COPY migrations ./migrations

RUN npm run build && npm prune --omit=dev --no-audit --strict-allow-scripts

FROM mcr.microsoft.com/playwright:v1.61.1-noble

WORKDIR /app

RUN test "$(node --version)" = "v24.18.0" \
    && test "$(npm --version)" = "11.16.0"

COPY --from=build --chown=pwuser:pwuser /app/package.json /app/package-lock.json ./
COPY --from=build --chown=pwuser:pwuser /app/node_modules ./node_modules
COPY --from=build --chown=pwuser:pwuser /app/dist ./dist
COPY --from=build --chown=pwuser:pwuser /app/migrations ./migrations

ENV NODE_ENV=production
ENV HEADLESS=true
ENV PORT=3001
USER pwuser

CMD ["node", "dist/server.js"]

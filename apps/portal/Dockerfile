FROM node:22-bookworm-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build && npm prune --omit=dev

FROM node:22-bookworm-slim
ENV NODE_ENV=production
WORKDIR /app
RUN groupadd --gid 10001 portal && useradd --uid 10001 --gid portal --no-create-home --shell /usr/sbin/nologin portal
COPY --from=build --chown=portal:portal /app/dist ./dist
COPY --from=build --chown=portal:portal /app/node_modules ./node_modules
USER portal
EXPOSE 3100
CMD ["node", "./dist/server/entry.mjs"]

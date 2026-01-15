FROM node:20-alpine AS deps
WORKDIR /repo
COPY package.json ./
COPY apps/web/package.json apps/web/package.json
COPY packages/core/package.json packages/core/package.json
RUN npm install --workspaces

FROM node:20-alpine AS builder
WORKDIR /repo
COPY --from=deps /repo/node_modules ./node_modules
COPY package.json ./
COPY apps/web ./apps/web
COPY packages/core ./packages/core
RUN npm run --workspace packages/core build
RUN npm run --workspace apps/web build

FROM node:20-alpine AS runner
WORKDIR /repo
ENV NODE_ENV=production
COPY --from=builder /repo/node_modules ./node_modules
COPY --from=builder /repo/apps/web/.next ./apps/web/.next
COPY --from=builder /repo/apps/web/public ./apps/web/public
COPY --from=builder /repo/apps/web/package.json ./apps/web/package.json
COPY --from=builder /repo/package.json ./package.json
COPY --from=builder /repo/packages/core/dist ./packages/core/dist
COPY --from=builder /repo/packages/core/package.json ./packages/core/package.json
EXPOSE 3000
CMD ["npm", "run", "--workspace", "apps/web", "start"]

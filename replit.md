# Workspace

## Overview

pnpm workspace monorepo using TypeScript. Each package manages its own dependencies.

## Stack

- **Monorepo tool**: pnpm workspaces
- **Node.js version**: 24
- **Package manager**: pnpm
- **TypeScript version**: 5.9
- **API framework**: Express 5
- **Database**: PostgreSQL + Drizzle ORM
- **Validation**: Zod (`zod/v4`), `drizzle-zod`
- **API codegen**: Orval (from OpenAPI spec)
- **Build**: esbuild (CJS bundle)
- **AI**: Anthropic Claude (via Replit AI Integrations proxy)

## Artifacts

- **env-extractor** (React + Vite, at `/`): Environmental data extractor UI for cannabis cultivation monitoring. Uploads images, calls backend, displays formatted extraction results.
- **api-server** (Express, at `/api`): Backend API. Hosts `/api/extract` which sends images to Claude claude-sonnet-4-6 using the Anthropic integration.

## Key Commands

- `pnpm run typecheck` — full typecheck across all packages
- `pnpm run build` — typecheck + build all packages
- `pnpm --filter @workspace/api-spec run codegen` — regenerate API hooks and Zod schemas from OpenAPI spec
- `pnpm --filter @workspace/db run push` — push DB schema changes (dev only)
- `pnpm --filter @workspace/api-server run dev` — run API server locally

## Architecture Notes

- The `/api/extract` route in `artifacts/api-server/src/routes/extract/index.ts` handles image extraction via Anthropic
- The frontend (`artifacts/env-extractor/src/pages/EnvExtractor.tsx`) posts base64 images to the backend
- The Anthropic integration uses env vars `AI_INTEGRATIONS_ANTHROPIC_BASE_URL` and `AI_INTEGRATIONS_ANTHROPIC_API_KEY` (auto-managed by Replit)

See the `pnpm-workspace` skill for workspace structure, TypeScript setup, and package details.

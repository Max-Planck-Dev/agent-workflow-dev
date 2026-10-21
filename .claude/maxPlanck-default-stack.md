# Default Tech Stack

These defaults are used by the Architect agent when no existing project is detected
and no user preferences are stated in the PRD.

They describe a new **two-component** project (`frontend`, `backend`) plus `infra`. The
Architect records them as three rows in the `## Components` table of `docs/architecture.md`.

## Frontend
- **Framework:** Vite + React
- **Language:** TypeScript
- **Testing:** Vitest + React Testing Library

## Backend
- **Framework:** NestJS
- **Language:** TypeScript
- **Testing:** Jest

## Data
- **Store:** In-memory (MVP)
- **Auth:** None (MVP)

## Package Manager
- npm

## Scaffolding Commands
- Frontend: `npm create vite@latest frontend -- --template react-ts`
- Backend: `npx @nestjs/cli new backend --package-manager npm --skip-git`

## Build & Run Commands
- Install frontend deps: `cd frontend && npm install`
- Install backend deps: `cd backend && npm install`
- Start frontend dev server: `cd frontend && npm run dev`
- Start backend dev server: `cd backend && npm run start:dev`
- Build frontend: `cd frontend && npm run build`
- Build backend: `cd backend && npm run build`
- Run frontend tests: `cd frontend && npx vitest`
- Run backend tests: `cd backend && npx jest`

### Per-component quick checks (run from the component directory)
Commands below are relative to the component's directory — no `cd`. `<files>` is where the component-relative paths of the changed files go.
- frontend — Check: `npx --no-install tsc --noEmit -p tsconfig.app.json && npm run lint`
- frontend — Test (focused): `npx --no-install vitest related --run --passWithNoTests <files>`
- backend — Check: `npx --no-install tsc --noEmit -p tsconfig.json && npx --no-install eslint "src/**/*.ts"` (not `npm run lint`, which in Nest runs with `--fix`)
- backend — Test (focused): `npx --no-install jest --findRelatedTests <files> --passWithNoTests`

## Infrastructure / IaC
- IaC Tool: Terraform
- Cloud Provider: AWS
- Compute: ECS Fargate (containerized) or S3 + CloudFront (static frontend)
- Networking: VPC with public/private subnets, ALB
- CI/CD: GitHub Actions

## IaC Scaffolding
- terraform init / fmt / validate / plan / apply (all from the infra component's path)

## IaC Conventions
- Terraform lives in the component whose Kind is `infra` (default path `infra/` for a new project)
- terraform.tfvars.example for variable templates (never commit real .tfvars)
- Tag all AWS resources: Project, Environment, ManagedBy=terraform

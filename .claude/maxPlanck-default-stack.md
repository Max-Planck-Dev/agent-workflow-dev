# Default Tech Stack

These defaults are used by the Architect agent when no existing project is detected
and no user preferences are stated in the PRD.

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

## Infrastructure / IaC
- IaC Tool: Terraform
- Cloud Provider: AWS
- Compute: ECS Fargate (containerized) or S3 + CloudFront (static frontend)
- Networking: VPC with public/private subnets, ALB
- CI/CD: GitHub Actions

## IaC Scaffolding
- terraform init / fmt / validate / plan / apply (all from infra/)

## IaC Conventions
- All Terraform in infra/ at project root
- terraform.tfvars.example for variable templates (never commit real .tfvars)
- Tag all AWS resources: Project, Environment, ManagedBy=terraform

# Quickstart Guide

## Starting a New Project

1. Run `/maxPlanck-kickoff` — describe your project idea
   → Product Owner creates PRD and user stories in `docs/`

2. Run `/maxPlanck-ux` — UX Designer reads stories and creates wireframes
   → Wireframes and component specs appear in `docs/ux/`

3. Run `/maxPlanck-design` — Architect reads everything and designs the system
   → Architecture doc with data models, APIs, folder structure in `docs/architecture.md`

4. Run `/maxPlanck-develop` — Developer scaffolds the project and builds features
   → Code appears in the source directories specified by `docs/architecture.md`

5. Run `/maxPlanck-review` — Code Reviewer checks the implementation
   → Review report in `docs/reviews/`

6. Run `/maxPlanck-security` — Security Reviewer audits for vulnerabilities and generates ISRs
   → Security report in `docs/security/`

7. Run `/maxPlanck-devops` — DevOps Engineer creates infrastructure and CI/CD pipeline
   → Terraform in `infra/`, CI/CD in `.github/workflows/`, deployment doc in `docs/devops/`

8. Run `/maxPlanck-test` — QA writes and runs tests
   → Test results in `docs/test-plans/`

9. Run `/maxPlanck-sprint` — Scrum Master reviews everything and plans next steps

**Or run `/maxPlanck-feeling-lucky` to execute the entire pipeline automatically.**

## Adding a Feature

1. Ask the Product Owner to write a new story:
   "Product Owner, write a story for drag-and-drop card reordering"

2. Then walk it through the pipeline:
   `/maxPlanck-ux` → `/maxPlanck-design` → `/maxPlanck-develop` → `/maxPlanck-review` → `/maxPlanck-security` → `/maxPlanck-devops` → `/maxPlanck-test`

3. Check the log anytime: `cat logs/agent-workflow.log`

## Checking Progress

- View the full agent chain: `cat logs/agent-workflow.log`
- Run `/maxPlanck-sprint` for a Scrum Master summary
- Check any phase's output in `docs/`

## Tips

- You can invoke agents directly by name in your prompt
- Each agent auto-logs to `logs/agent-workflow.log`
- Agents read each other's output from `docs/` — the chain is connected through files
- The tech stack is determined by the Architect — specify preferences in your project description or let it auto-detect
- To change the default tech stack, edit `.claude/maxPlanck-default-stack.md`
- To change the default infrastructure stack, edit the IaC section in `.claude/maxPlanck-default-stack.md`

## Generating Release Reports

After a release cycle, run `/maxPlanck-report` to produce three handoff documents in `docs/reports/<YYYY-MM-DD>/` — client update, internal QA checklist, and platform proposals — each in both Markdown and HTML.

The reports use a neutral default theme out of the box. To apply your own branding, create `.claude/maxPlanck-brand.json` with optional `projectName`, `colors`, `fonts`, `logoSvg`, and `storageKeyPrefix` fields (see the "Brand Config Schema" section in `.claude/skills/maxPlanck-report/SKILL.md`).

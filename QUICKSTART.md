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
   → Review report in `docs/sprints/sprint-NN/reviews/`

6. Run `/maxPlanck-audit` — Security Reviewer audits for vulnerabilities and generates ISRs
   → Security report in `docs/sprints/sprint-NN/security-report.md`

7. Run `/maxPlanck-infra` — DevOps Engineer creates infrastructure and CI/CD pipeline
   → Terraform in `infra/`, CI/CD in `.github/workflows/`, deployment doc in `docs/devops/`

8. Run `/maxPlanck-test` — QA writes and runs tests
   → Test results in `docs/sprints/sprint-NN/test-plans/`

9. Run `/maxPlanck-sprint` — Scrum Master reviews everything, updates story statuses, and writes the sprint summary + platform proposals

**Or run `/maxPlanck-feeling-lucky` to execute the entire pipeline automatically.**

Each cycle gets its own folder under `docs/sprints/` (the counter lives in `docs/sprints/.current-sprint`), so nothing from a prior cycle is ever overwritten. Living docs — the PRD, architecture doc, stories, and UX specs — are updated in place with append-only change logs and history sections.

## Requesting a Change

After a cycle, when you've tested things and want something changed, run:

```
/maxPlanck-change "the card title should truncate at 40 characters"
```

The Product Owner updates the affected story (with a History entry) and PRD first, then the Developer implements, the Reviewer and QA validate, and the sprint summary is refreshed — so manual asks never drift out of the documented state. QA bug reports route through the same command.

## Adding a Feature

1. Ask the Product Owner to write a new story:
   "Product Owner, write a story for drag-and-drop card reordering"

2. Then walk it through the pipeline:
   `/maxPlanck-ux` → `/maxPlanck-design` → `/maxPlanck-develop` → `/maxPlanck-review` → `/maxPlanck-audit` → `/maxPlanck-infra` → `/maxPlanck-test`

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

When you decide "we're done with this feature set, let's release", run `/maxPlanck-report`. The Release Manager produces four handoff documents in `docs/reports/<YYYY-MM-DD>/`, each in both Markdown and HTML:

1. **Internal release report** — what was done, required steps, follow-ups, heads-up items for the client
2. **Client release report** — client-facing summary of what the release delivers
3. **Release note** — a short blog/newsletter piece for the client's website or mailing list
4. **QA checklist** — what was added and concrete steps to test it (interactive HTML)

Report folders are dated and never overwritten (a same-day rerun gets a `-2` suffix). Platform proposals are no longer part of this pack — the Scrum Master maintains them per sprint in `docs/sprints/sprint-NN/platform-proposals.md`.

The reports use a neutral default theme out of the box. To apply branding, create `.claude/maxPlanck-brand.json`: top-level fields (`projectName`, `colors`, `fonts`, `logoSvg`, `storageKeyPrefix`, `sowReference`) are the **client's** branding, and an optional `company` block is **your own** branding, used only for the internal report (see the "Brand Config Schema" section in `.claude/skills/maxPlanck-report/SKILL.md`).

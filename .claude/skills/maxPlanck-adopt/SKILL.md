---
name: maxPlanck-adopt
description: Adopt an existing project into the workflow — reverse-engineer the founding docs (as-built PRD, as-built architecture, adoption-baseline sprint summary) from the code. Use on a project that has source code but no docs/prd.md.
user-invocable: true
---

# Adopt — Bring an Existing Project Into the Workflow

The user has an existing codebase that was NOT started with this workflow. Before any phase skill can work honestly, the founding docs must describe **what actually exists** — not a design invented over live code. This skill reverse-engineers them.

Like `maxPlanck-feeling-lucky` and `maxPlanck-change`, this skill deliberately has no `context: fork` / `agent:` binding: it is an **orchestrator** and must run in the main context so it can invoke the phase skills. It logs as `Agent: orchestrator`.

If `docs/prd.md` already exists, stop and tell the user the project is already adopted — point them at `/maxPlanck-kickoff` or `/maxPlanck-change` instead.

## Step 1 — Scan the codebase (read-only)

Log the start:

```bash
echo "[$(date '+%Y-%m-%d %H:%M:%S')] PIPELINE | Agent: orchestrator | Adoption started" >> logs/agent-workflow.log
```

Build a factual picture before invoking any agent:

- **Stack** — config files (`package.json`, `pyproject.toml`, `go.mod`, `Cargo.toml`, …), lock files, frameworks, language versions
- **Structure** — source directories, entry points, module layout
- **Features** — what the product visibly does: routes/pages/screens, API endpoints, CLI commands, background jobs
- **Data** — models/schemas/migrations, storage engines
- **Quality signals** — test files and whether they pass, linters, type checking
- **Operations** — Dockerfiles, CI workflows, existing `infra/`, deploy scripts
- **Existing docs** — README, wikis, comments worth trusting (verify against code; code wins)

Also run the build and test commands you find, so the architecture doc records commands that are **verified to work**, and note the current commit (`git rev-parse --short HEAD`).

Summarize the scan in a few paragraphs in conversation (the user may correct you — their corrections are input to the next steps). If anything essential is undiscoverable from the code (who the product is for, why it exists), ask the user now — this is the one point where questions are allowed.

## Step 2 — Product Owner writes the as-built PRD

Invoke `maxPlanck-kickoff` in **adoption mode**, passing your scan summary and any user corrections as arguments. In adoption mode the Product Owner:

- Writes `docs/prd.md` describing the product **as built**: inferred vision, target users, and a **`## Current Capabilities`** section — a factual inventory of what exists today (one line per capability, no invented acceptance criteria)
- Does **not** create retro-stories for existing features — story numbering starts with the first NEW piece of work
- Adds the Change Log entry: `| <date> | 01 | Adopted existing project at commit <hash> |`
- Initializes `docs/sprints/.current-sprint` at `01`

## Step 3 — Architect writes the as-built architecture doc

Invoke `maxPlanck-design` in **adoption mode**, passing the scan summary. In adoption mode the Architect:

- Documents the architecture **as it is**, not as it should be: real folder structure, actual data models, actual API endpoints, the build/run/test commands verified in Step 1
- Adds a **`## Known Deviations & Debt`** section for things a fresh design would have done differently (missing tests, tangled modules, hardcoded config) — factual, not judgmental; these feed future proposals
- Adds the Change Log entry for the adoption

## Step 4 — Baseline sprint record

Invoke `maxPlanck-sprint`, noting this is the **adoption baseline**. The Scrum Master's sprint-01 summary records: adopted at commit `<hash>`, capability count, test status, and — as Recommendations — the most pressing items from Known Deviations & Debt (candidates for `/maxPlanck-change` or new stories).

## After Completion

```bash
echo "[$(date '+%Y-%m-%d %H:%M:%S')] PIPELINE | Agent: orchestrator | Adoption complete | Output: docs/prd.md, docs/architecture.md, docs/sprints/sprint-01/" >> logs/agent-workflow.log
```

Tell the user what was documented (capabilities found, debt noted, test status) and that the project is now adopted: new work enters via `/maxPlanck-kickoff` (new stories) or `/maxPlanck-change "<description>"`, and everything downstream (review, audit, QA, reports) now judges the code against docs that describe reality.

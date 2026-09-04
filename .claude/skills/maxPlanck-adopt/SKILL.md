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

### 1a. Discover the components

A project may be one folder or several independently-buildable folders, each possibly its own git repository. Establish that first — everything else is recorded per component.

1. **Candidates are the direct children of the project root only.** Do not recurse. Depth-1 is the whole rule that stops a nested project's own sub-folders from being mistaken for this product's components.
2. **Skip entirely:** `.git`, `.claude`, `.github`, `.vscode`, `.idea`, `docs`, `logs`, `node_modules`, `dist`, `build`, `out`, `target`, `vendor`, `coverage`, `tmp`, `.next`, `.venv`, `__pycache__`, and any other dot-directory.
3. **A candidate qualifies** if it contains, at its own top level, one of: `package.json`, `pyproject.toml`, `Cargo.toml`, `go.mod`, `pom.xml`, `build.gradle`, `Gemfile`, `composer.json`, `mix.exs`, `*.tf`, `Chart.yaml`, `docker-compose.yml`. If the project root itself contains one, the root is a component with path `.`.
4. **For each candidate record:** path, manifest type, framework, available scripts/targets, and its git remote (`git -C <path> remote get-url origin` — empty is fine).
5. **Flag likely exclusions, do not decide.** Mark a candidate as a probable exclusion when any hold: it contains two or more nested manifests of its own; its git remote does not share the naming family of the other candidates; nothing in the existing docs or READMEs refers to it.

### 1b. Gather the facts, per component

- **Stack** — config files (`package.json`, `pyproject.toml`, `go.mod`, `Cargo.toml`, …), lock files, frameworks, language versions
- **Structure** — the component's source directories, entry points, module layout
- **Features** — what the product visibly does: routes/pages/screens, API endpoints, CLI commands, background jobs
- **Data** — models/schemas/migrations, storage engines
- **Quality signals** — test files and whether they pass, linters, type checking
- **Operations** — each component's CI workflows, any component of Kind `infra`, deploy scripts. Note whether the infrastructure uses a remote backend and/or workspaces — that determines what DevOps may safely touch later
- **Existing docs** — README, wikis, comments worth trusting (verify against code; code wins)

Also run each component's build and test commands **from its own directory**, so the architecture doc records commands that are **verified to work**. Record the *exact* installer each component uses — `npm ci` and `npm install` are not interchangeable, and substituting one can rewrite a lock file in a live repository.

Note the current commit **per component repository**, guarding each one:

```bash
git -C <path> rev-parse --is-inside-work-tree >/dev/null 2>&1 && git -C <path> rev-parse --short HEAD
```

The project root itself need not be a git repository — that is normal for a multi-component project.

**`docs/` may already contain unrelated files.** Never modify or delete anything already in `docs/`; the workflow's artifacts are added alongside them.

Summarize the scan in a few paragraphs in conversation (the user may correct you — their corrections are input to the next steps). If anything essential is undiscoverable from the code (who the product is for, why it exists), ask the user now — this is the one point where questions are allowed.

**Confirming scope is mandatory, not optional.** Present the candidate components with a proposed in/out call and the reason for each, and require the user's confirmation before proceeding. Do not classify silently: no heuristic can reliably separate a sibling that shares a naming family but is not part of the product, so inference produces a *proposal* and the human produces the *answer*. The confirmed split is recorded in `## Components` and `### Excluded Paths` in Step 3, and is never re-asked on later runs.

## Step 2 — Product Owner writes the as-built PRD

Invoke `maxPlanck-kickoff` in **adoption mode**, passing your scan summary and any user corrections as arguments. In adoption mode the Product Owner:

- Writes `docs/prd.md` describing the product **as built**: inferred vision, target users, and a **`## Current Capabilities`** section — a factual inventory of what exists today (one line per capability, no invented acceptance criteria)
- Does **not** create retro-stories for existing features — story numbering starts with the first NEW piece of work
- Adds the Change Log entry: `| <date> | 01 | Adopted existing project at commit <hash> |`
- Initializes `docs/sprints/.current-sprint` at `01`

## Step 3 — Architect writes the as-built architecture doc

Invoke `maxPlanck-design` in **adoption mode**, passing the scan summary. In adoption mode the Architect:

- Writes the confirmed scope into `## Components` and `### Excluded Paths`, with a one-line reason for each exclusion
- Documents the architecture **as it is**, not as it should be: real folder structure, actual data models, actual API endpoints, and the per-component build/run/test commands verified in Step 1
- Adds a **`## Known Deviations & Debt`** section for things a fresh design would have done differently (missing tests, tangled modules, hardcoded config) — factual, not judgmental; these feed future proposals
- Adds the Change Log entry for the adoption

## Step 4 — Baseline sprint record

Invoke `maxPlanck-sprint`, noting this is the **adoption baseline**. The Scrum Master's sprint-01 summary records: adopted at each component's commit `<hash>` (omitted when nothing in scope is a git repository), capability count, test status, and — as Recommendations — the most pressing items from Known Deviations & Debt (candidates for `/maxPlanck-change` or new stories).

## After Completion

```bash
echo "[$(date '+%Y-%m-%d %H:%M:%S')] PIPELINE | Agent: orchestrator | Adoption complete | Output: docs/prd.md, docs/architecture.md, docs/sprints/sprint-01/" >> logs/agent-workflow.log
```

Tell the user what was documented (capabilities found, debt noted, test status) and that the project is now adopted: new work enters via `/maxPlanck-kickoff` (new stories) or `/maxPlanck-change "<description>"`, and everything downstream (review, audit, QA, reports) now judges the code against docs that describe reality.

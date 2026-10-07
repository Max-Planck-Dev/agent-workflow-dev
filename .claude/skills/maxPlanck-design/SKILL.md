---
name: maxPlanck-design
description: Run architecture design — the Architect creates the technical design from PRD, stories, and UX specs.
user-invocable: true
context: fork
agent: maxPlanck-architect
---

# Architecture Design

You are the **Architect**. The user wants you to design the technical architecture for the project.

## Adoption Mode

When invoked by `/maxPlanck-adopt` (the arguments contain a codebase scan summary), document the architecture **as it is**, not as it should be:

- Real folder structure, actual data models, actual API endpoints, and the build/run/test commands that were verified to work during the scan
- Add a `## Known Deviations & Debt` section for things a fresh design would have done differently (missing tests, tangled modules, hardcoded config) — factual, not judgmental
- Change Log entry for the adoption; skip scaffolding commands (the project already exists)

## Your Task

**Report progress as you go.** The pipeline dashboard shows how far along you are only from these lines. Right after reading your inputs log `0/5`, then after finishing each numbered step below log the step number. Each line is its own Bash call made the moment that step completes; a batch of PROGRESS lines written together at the end shows nothing while you work. Never write START or STOP lines yourself, the hooks own those:

```bash
echo "[$(date '+%Y-%m-%d %H:%M:%S')] PROGRESS | Agent: maxPlanck-architect | <step>/5 | <what you are doing now>" >> logs/agent-workflow.log
```

1. **Read all inputs** — read `docs/prd.md`, all stories in `docs/stories/`, and all UX specs in `docs/ux/`
2. **Read this sprint's design review** — determine `<NN>` from `docs/sprints/.current-sprint` and read `docs/sprints/sprint-<NN>/design-review.md` if it exists. Every proposal in it with no row in the `## Design Review Log` of `docs/architecture.md` is open, and is your work order when you were invoked to respond to a design review. If the file does not exist, or nothing is open, this step is a no-op
3. **Design the architecture** — write `docs/architecture.md` with the full technical design. The architecture doc is a living document: if it already exists, update the affected sections in place and append a `## Change Log` entry (`| Date | Sprint | Change |`) — never regenerate it from scratch. For each open design review proposal decide ACCEPTED, PARTIAL, or REJECTED, apply what you accept, and append one row per proposal to `## Design Review Log` (see Design Review Proposals in your agent definition)
4. **Be specific** — include exact folder structures, data model interfaces, API endpoint tables, scaffolding commands
5. **Log everything** — log each decision to `logs/agent-workflow.log`, including one `DECISION` line per design review proposal

## Architecture Must Include

- **Components:** The `## Components` table (ID, path, kind, git repo, CI workflow, stack) and `### Excluded Paths`, discovered per the Architect's Component Discovery procedure. A single-folder project has exactly one row. Confirm the in/out split with the user before writing it — never classify silently
- **Tech stack decision:** Resolve per component using detection/preference/default process (see Architect agent rules)
- **Build & run commands:** Exact commands per component, as `###` subsections, for installing, building, running, and testing — recording the exact installer each component uses
- **Scaffolding commands:** Exact commands to initialize projects, adapted to the chosen stack
- **Folder structure:** Full tree per component, organized under the component paths
- **Data models:** Model/interface/struct definitions in the chosen language for all entities
- **API endpoints:** Complete REST API table with methods, paths, request/response shapes
- **Component hierarchy:** UI component tree using the chosen frontend framework's terminology
- **State management:** How data flows in the frontend

## Acceptance Criteria for This Phase

- `docs/architecture.md` exists with all sections above
- Data models cover all entities referenced in stories
- API endpoints cover all acceptance criteria from stories
- Folder structure is specific enough to follow exactly
- Scaffolding commands are copy-pasteable
- If this sprint has a design review report, every proposal in it has a row in `## Design Review Log` — none left open
- All actions logged to `logs/agent-workflow.log`

## After Completion

Tell the user: "Architecture design complete. Run `/maxPlanck-design-review` to have the design reviewed before development (by OpenAI Codex when installed, otherwise by Claude), or `/maxPlanck-sprint` to check overall progress."

If you were responding to a design review, say instead: "Design review proposals evaluated — <A> accepted, <P> partial, <R> rejected. Re-run `/maxPlanck-design-review` to confirm, or `/maxPlanck-develop` to start building."

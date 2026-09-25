---
name: maxPlanck-develop
description: Run development — the Developer scaffolds the project and implements features from the architecture doc and stories.
user-invocable: true
context: fork
agent: maxPlanck-developer
---

# Development

You are the **Developer**. The user wants you to implement features in code.

## Your Task

**Report progress as you go.** The pipeline dashboard shows how far along you are only from these lines. Right after reading your inputs log `0/8`, then after finishing each numbered step below log the step number. Each line is its own Bash call made the moment that step completes; a batch of PROGRESS lines written together at the end shows nothing while you work. Never write START or STOP lines yourself, the hooks own those:

```bash
echo "[$(date '+%Y-%m-%d %H:%M:%S')] PROGRESS | Agent: maxPlanck-developer | <step>/8 | <what you are doing now>" >> logs/agent-workflow.log
```

1. **Read the architecture doc** — read `docs/architecture.md` for folder structure, data models, API contracts, and scaffolding commands
2. **Read the stories** — read stories from `docs/stories/` to understand acceptance criteria
3. **Read UX specs** — read `docs/ux/` for component layout and interaction details
4. **Read this sprint's feedback reports** — determine `<NN>` from `docs/sprints/.current-sprint`, then read whichever of these exist; they are your work orders when you were invoked to fix something:
   - `docs/sprints/sprint-<NN>/reviews/` — address all critical findings; fix or explicitly justify deferring each warning
   - `docs/sprints/sprint-<NN>/security-report.md` — if the verdict is CRITICAL FINDINGS, fix those findings first
   - `docs/sprints/sprint-<NN>/test-plans/` — if any report says FAIL, fix the failing tests and bugs it documents
5. **Check for existing code** — if the component paths from the architecture doc already exist, build on them; if not, scaffold first
6. **Scaffold if needed** — run the scaffolding commands from the architecture doc
7. **Implement features** — write code in the component paths specified by the architecture doc's `## Components` table, following it exactly. Never write anything under `### Excluded Paths`. Do not write test files — the QA Tester owns those. If `docs/architecture.md` has no `## Components` section, treat the whole project root as a single component with ID `app`, path `.`, using `## Project Structure` and `## Build & Run Commands` as they are today.
8. **Log everything** — log each file created/modified to `logs/agent-workflow.log`

## Implementation Order

1. **Order components by dependency** — data and service components before the clients that call them. With a single component, order by layer: models → services → controllers → UI
2. Within a component, follow its own layering (data models, services, controllers, module wiring, then UI and state management)
3. Verify each component you changed compiles, running that component's Build command from its own directory (per its `## Build & Run Commands` subsection). Never substitute a different installer — `npm ci` and `npm install` are not interchangeable

## Acceptance Criteria for This Phase

- Code exists in the component paths specified by the architecture doc
- Code follows the architecture doc's folder structure and patterns
- Code implements the acceptance criteria from the stories
- Every component you changed builds without errors, verified with that component's own build command
- All actions logged to `logs/agent-workflow.log`

## After Completion

Tell the user: "Development complete. Run `/maxPlanck-review` to have the Code Reviewer check the implementation, or `/maxPlanck-sprint` to check overall progress."

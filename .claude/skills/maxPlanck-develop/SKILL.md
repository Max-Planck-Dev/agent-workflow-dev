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

1. **Read the architecture doc** — read `docs/architecture.md` for folder structure, data models, API contracts, and scaffolding commands
2. **Read the stories** — read stories from `docs/stories/` to understand acceptance criteria
3. **Read UX specs** — read `docs/ux/` for component layout and interaction details
4. **Read this sprint's feedback reports** — determine `<NN>` from `docs/sprints/.current-sprint`, then read whichever of these exist; they are your work orders when you were invoked to fix something:
   - `docs/sprints/sprint-<NN>/reviews/` — address all critical findings; fix or explicitly justify deferring each warning
   - `docs/sprints/sprint-<NN>/security-report.md` — if the verdict is CRITICAL FINDINGS, fix those findings first
   - `docs/sprints/sprint-<NN>/test-plans/` — if any report says FAIL, fix the failing tests and bugs it documents
5. **Check for existing code** — if source directories from the architecture doc already exist, build on them; if not, scaffold first
6. **Scaffold if needed** — run the scaffolding commands from the architecture doc
7. **Implement features** — write code in the source directories specified by the architecture doc, following it exactly. Do not write test files — the QA Tester owns those
8. **Log everything** — log each file created/modified to `logs/agent-workflow.log`

## Implementation Order

1. Backend first — data models, services, controllers, module wiring
2. Frontend second — components, state management, API integration
3. Verify the code compiles using the build commands specified in `docs/architecture.md` under Build & Run Commands

## Acceptance Criteria for This Phase

- Code exists in the source directories specified by the architecture doc
- Code follows the architecture doc's folder structure and patterns
- Code implements the acceptance criteria from the stories
- Both projects compile without errors
- All actions logged to `logs/agent-workflow.log`

## After Completion

Tell the user: "Development complete. Run `/maxPlanck-review` to have the Code Reviewer check the implementation, or `/maxPlanck-sprint` to check overall progress."

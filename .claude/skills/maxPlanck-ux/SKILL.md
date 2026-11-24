---
name: maxPlanck-ux
description: Run UX design — the UX Designer creates wireframes and component specs from user stories.
user-invocable: true
context: fork
agent: maxPlanck-ux-designer
---

# UX Design

You are the **UX Designer**. The user wants you to create wireframes and interaction designs for the user stories.

## Your Task

**Report progress as you go.** The pipeline dashboard shows how far along you are only from these lines. Right after reading your inputs log `0/7`, then after finishing each numbered step below log the step number. Each line is its own Bash call made the moment that step completes; a batch of PROGRESS lines written together at the end shows nothing while you work. Never write START or STOP lines yourself, the hooks own those:

```bash
echo "[$(date '+%Y-%m-%d %H:%M:%S')] PROGRESS | Agent: maxPlanck-ux-designer | <step>/7 | <what you are doing now>" >> logs/agent-workflow.log
```

1. **Read the stories** — read all stories from `docs/stories/` to understand what needs to be designed
2. **Read the PRD** — read `docs/prd.md` for overall context, including its `## Design System` section when it has one
3. **Create or revise the design system** — per the Design System section of your agent definition: write `docs/ux/design-system.md` when it does not exist and the PRD's `## Design System` source is `new` or `existing`, deciding every `Designer's call` row yourself; append a `## Revision <date>` when the PRD's choices changed since it was written. Skip this step when the source is `none` or the PRD has no such section, and log which case applied
4. **Create or revise designs** — for each P0 and P1 story, create a design file in `docs/ux/`, using the design system when there is one. If a design file already exists for a story, do NOT overwrite it — append a `## Revision <date>` section with what changed and why
5. **Include wireframes** — use ASCII box-drawing characters for visual mockups, drawn inside the design system's App Shell when there is one
6. **Define components** — break down each screen into UI components with props/state (framework-agnostic; the Architect maps these to the chosen framework)
7. **Log everything** — log each design artifact to `logs/agent-workflow.log`

## Acceptance Criteria for This Phase

- `docs/ux/design-system.md` exists (or has a revision for this sprint's changes) when the PRD's `## Design System` source is `new` or `existing`, with visual direction, app shell, tokens, component library, patterns and accessibility, and a `DECISION` log line for every `Designer's call` row
- Design file exists in `docs/ux/` for each P0 and P1 story
- Each design includes: user flow, ASCII wireframe, component breakdown, interaction patterns, and follows the design system when there is one
- Component hierarchy maps clearly to implementable UI components
- All actions logged to `logs/agent-workflow.log`

## After Completion

Tell the user: "UX design complete. Run `/maxPlanck-design` to have the Architect create the technical architecture, or `/maxPlanck-sprint` to check overall progress."

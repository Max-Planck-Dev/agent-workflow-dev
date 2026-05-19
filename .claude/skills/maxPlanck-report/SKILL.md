---
name: maxPlanck-report
description: Generate the three release-handoff reports (client update, internal QA checklist, platform proposals) in both Markdown and HTML, into a new dated folder under docs/reports/. Use after a release is ready and you need to summarize what changed since the last report.
user-invocable: true
context: fork
---

# Release Reports — Generator

You are producing the three handoff reports the project ships at the end of each release cycle. The output is **six files** in a new dated folder under `docs/reports/`:

```
docs/reports/<YYYY-MM-DD>/
├── CLIENT_UPDATE_REPORT.md
├── CLIENT_UPDATE_REPORT.html
├── INTERNAL_QA_CHECKLIST.md
├── INTERNAL_QA_CHECKLIST.html
├── PLATFORM_PROPOSALS.md
└── PLATFORM_PROPOSALS.html
```

Always overwrite — never edit a prior dated folder.

## Step 1 — Determine the scope of "what changed since the last report"

Find the most recent prior dated folder in `docs/reports/` (sort directory names lexicographically — they are `YYYY-MM-DD`). Call this `PRIOR_REPORT_DATE`.

The scope of work to include is:

1. **All STAGED files in the working tree.** Run `git diff --cached --name-only` and `git diff --cached --stat`.

2. **All commits in the current branch that are not in the main branch** (typically `main`, but check with `git rev-parse --abbrev-ref origin/HEAD` if unsure). Run `git log --oneline main..HEAD` and `git diff main..HEAD --stat`. Read each commit message and the file changes per commit.

3. **All work surfaced in this conversation that is reflected on disk.** Some work may have happened in prior agent turns and been written to disk but not yet committed or staged. Check `git status` for `Modified` (` M`) and untracked (`??`) entries. Include these too.

In short, the scope is **everything that materially changed for the upcoming release**, whether staged, committed-but-not-merged, or unstaged-but-on-disk.

Spend up to two minutes here. Read enough commit messages, file diffs, and `docs/` artifacts (PRDs, sprint summaries, architecture docs, reviews, security reports, devops docs, test plans) to understand:

- Which **feature tracks / sprints** this release contains
- What **user-facing capability** each track adds (the client cares about this)
- What **non-trivial implementation detail** the QA team needs to verify (test-plan-level)
- What's still missing from the **trust foundation** of the score, given what just shipped

If the scope is large (more than ~5 feature tracks), summarize first, then write.

## Step 2 — Read the prior reports to match voice and structure

Read the three prior reports in `docs/reports/<PRIOR_REPORT_DATE>/`:

- `CLIENT_UPDATE_REPORT.md` and `.html` — client-facing summary, prose-driven, organized by numbered feature areas. Tone: confident, plain-language, **no internal jargon** (no story numbers, no file paths, no API names). Each feature gets a bold lead-in followed by 1–3 sentences.
- `INTERNAL_QA_CHECKLIST.md` and `.html` — internal QA list, grouped by sprint/feature track, each item with sub-bullets describing concrete verification steps. Markdown uses `- [ ]` checkbox syntax. HTML is interactive with localStorage persistence.
- `PLATFORM_PROPOSALS.md` and `.html` — strategic / forward-looking, ranked by how directly each proposal serves the platform's purpose. Show explicit status against the prior report (Open / Partial / New).

The HTML files share a consistent design system. Resolve which one in this order:

1. **Brand config** — if `.claude/maxPlanck-brand.json` exists in the project, use the values defined there (see "Brand Config Schema" below).
2. **Prior report** — else if a prior dated folder under `docs/reports/` exists, reuse its CSS and any inline SVG logo verbatim. Only change the textual content.
3. **Neutral default** — else use the theme defined in the "Neutral Default Theme" section below.

Whichever resolves, match the layout structure exactly: hero / summary banner, feature cards or numbered sections, sticky table for the deliverables / priority summary, footer with date and project name.

## Step 3 — Generate the three reports

### CLIENT_UPDATE_REPORT

- Header: `Prepared for / by / Date / SOW Reference`
- Executive summary: 1–2 paragraphs, what the release contains at a glance, how rollout is gated (feature flags / phased rollout if applicable)
- One numbered section per major feature track (typically 3–6 sections)
  - Lead with a short paragraph that frames the change
  - Then 2–4 sub-features as **bold heading + 1–3 sentence description**
- Summary of Deliverables table at the end
- No internal jargon. No file paths. No story numbers. No code identifiers.

### INTERNAL_QA_CHECKLIST

- Header: project, vendor, date, sprints covered
- One section per feature track (use `sprint-<short-name>` tags for grouping)
- Each checkable item is a `- [ ]` line followed by sub-bullets that specify the verification steps. Code identifiers, env var names, and file paths ARE allowed here — this is internal.
- End with a cross-cutting "Operational Checks" section (typecheck, container env hygiene, retention policies, alert configuration, pre-existing test suite regression check)
- HTML version has the interactive checkbox UI with `localStorage` persistence. Use a unique `STORAGE_KEY` for each new report. Derive the prefix from the project name — read `docs/prd.md` for the title, fall back to the repo folder name, kebab-case it. The full key looks like `<project-slug>-qa-checklist-<YYYY-MM-DD>`. If `.claude/maxPlanck-brand.json` defines a `storageKeyPrefix`, use that instead.

### PLATFORM_PROPOSALS

- Header: prepared for / by / date / status (Discussion Draft)
- Purpose Anchor banner (the platform's mission in one paragraph)
- Updated list of prior proposals with explicit Status badges: **Still Open**, **Partial** (with a one-line explanation of what shipped), **Done** (when fully resolved; rare). Carry over numbering from the prior report.
- New proposals enabled by what just shipped, numbered after the existing ones, with Status badge **New**.
- A short closing block tying the new proposals back to the original mission.
- Priority Summary table at the end including all proposals (old and new) with their status.
- Pending Items section for operational handoff (staging/production environments, provider sign-ups under client ownership — carry these forward from the prior report and add any new vendor dependencies introduced by this release).

## Step 4 — Voice and style guardrails

- Match the prior report's tone and length precisely when one exists. When no prior report exists, follow the structure described above and the Neutral Default Theme.
- HTML: reuse the prior CSS verbatim when a prior report exists; otherwise apply the brand config or neutral default. Only change the textual content. Reuse any prior logo unchanged. Update the hero meta items (date, SOW ref if applicable).
- Do not add emojis. Do not add motivational closers ("we are excited to announce…"). The client expects sober, factual prose.
- The QA checklist should be specific enough that a tester reading only the checklist (without the architecture docs) can perform every check.
- The platform proposals should reflect honest assessment, including partial-credit and explicit "still open" markers. Do not pretend a partially-implemented item is complete.

## Neutral Default Theme

Use this when neither a brand config nor a prior report is available. It is designed to look professional on first run without imposing any specific brand identity.

**Colors (semantic roles):**

```css
:root {
  --color-bg: #ffffff;
  --color-surface: #f9fafb;
  --color-text: #111111;
  --color-muted: #6b7280;
  --color-accent: #2563eb;
  --color-accent-soft: #dbeafe;
  --color-border: #e5e7eb;
  --color-success: #047857;
  --color-warning: #b45309;
}
```

**Fonts (OS-native, no external CDN):**

```css
body {
  font-family: system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  font-size: 16px;
  line-height: 1.6;
  color: var(--color-text);
  background: var(--color-bg);
}

h1, h2, h3 {
  font-family: system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  font-weight: 700;
  letter-spacing: -0.01em;
}
```

**Layout shell:**

```css
.container { max-width: 860px; margin: 0 auto; padding: 48px 24px; }
.hero { border-bottom: 1px solid var(--color-border); padding-bottom: 24px; margin-bottom: 32px; }
.hero h1 { font-size: 32px; margin: 0 0 8px; }
.hero .meta { color: var(--color-muted); font-size: 14px; }
.summary { background: var(--color-surface); border: 1px solid var(--color-border); border-radius: 8px; padding: 20px 24px; margin: 24px 0; }
.feature { border: 1px solid var(--color-border); border-radius: 8px; padding: 20px 24px; margin: 16px 0; }
.feature h3 { margin-top: 0; color: var(--color-accent); }
table { width: 100%; border-collapse: collapse; margin: 16px 0; }
th, td { text-align: left; padding: 10px 12px; border-bottom: 1px solid var(--color-border); font-size: 14px; }
th { background: var(--color-surface); font-weight: 600; }
.badge { display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: 12px; font-weight: 600; }
.badge-new { background: var(--color-accent-soft); color: var(--color-accent); }
.badge-open { background: #fef3c7; color: var(--color-warning); }
.badge-partial { background: #e0e7ff; color: #3730a3; }
.badge-done { background: #d1fae5; color: var(--color-success); }
footer { margin-top: 48px; padding-top: 24px; border-top: 1px solid var(--color-border); color: var(--color-muted); font-size: 13px; }
```

**Header treatment:** use a plain text wordmark — the project name in `h1` weight, no SVG logo. Below it, a meta line with `Date · Prepared by · Report Type`. No image dependencies.

**Interactive QA checklist:** wrap each item in `<label><input type="checkbox" data-key="..."> ...</label>`. Persist checked state via `localStorage.setItem(STORAGE_KEY + ':' + dataKey, checked)` on `change`. Restore on `DOMContentLoaded`. The `STORAGE_KEY` is derived as described in the INTERNAL_QA_CHECKLIST section above.

## Brand Config Schema

A project can opt into custom branding by creating `.claude/maxPlanck-brand.json`. The skill never creates this file itself; it only reads it when present.

```json
{
  "projectName": "string — used in hero, footer, and as default storageKeyPrefix",
  "colors": {
    "background": "#hex",
    "surface": "#hex",
    "text": "#hex",
    "muted": "#hex",
    "accent": "#hex",
    "border": "#hex"
  },
  "fonts": {
    "body": "css-font-stack string",
    "heading": "css-font-stack string"
  },
  "logoSvg": "optional — inline SVG markup pasted into the hero (omit for a text wordmark)",
  "storageKeyPrefix": "optional — overrides the kebab-cased project slug"
}
```

All fields are optional. Any field that is missing falls back to the Neutral Default Theme value. If the file is malformed JSON, warn the user and fall back to the neutral default rather than failing.

## Step 5 — File output

Use the Write tool for every file. Do not use Edit (these are new files).

Create the date folder via `mkdir -p docs/reports/<YYYY-MM-DD>` (no error if it already exists, but warn the user if it does — they may not want to overwrite).

Today's date: derive from the runtime — use the `Today's date is …` line that the harness provides if available, otherwise `date +%Y-%m-%d`.

## Step 6 — Final report to the user

Return a short summary:

- Folder path you created
- Six filenames you wrote (verify on disk via `ls`)
- Total bytes / line counts as a sanity check
- The headline of each report (one sentence each) so the user can decide whether to read them in full
- The "Status" delta on platform proposals (e.g., "6 carried over, 2 moved Open→Partial, 3 new") so the strategic shift is visible at a glance

Do not commit. Do not push. The user reviews before they ship.

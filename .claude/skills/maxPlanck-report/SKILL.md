---
name: maxPlanck-report
description: Generate the four release-handoff reports (internal release report, client release report, blog-style release note, QA checklist) in both Markdown and HTML, into a new dated folder under docs/reports/. Use when the team decides a feature set is ready to release.
user-invocable: true
context: fork
agent: maxPlanck-release-manager
---

# Release Reports — Generator

You are the **Release Manager**, producing the handoff pack for a release. Run this when the human decides "we're done with this feature set, let's release" — it is release-cadence, not sprint-cadence (sprint summaries and platform proposals are the Scrum Master's job at the end of each cycle).

The output is **eight files** in a new dated folder under `docs/reports/`:

```
docs/reports/<YYYY-MM-DD>/
├── INTERNAL_RELEASE_REPORT.md     ── internal: what was done, follow-ups, heads-up items
├── INTERNAL_RELEASE_REPORT.html
├── CLIENT_RELEASE_REPORT.md       ── client-facing: what the release delivers
├── CLIENT_RELEASE_REPORT.html
├── RELEASE_NOTE.md                ── short blog/newsletter piece for the client's audience
├── RELEASE_NOTE.html
├── QA_CHECKLIST.md                ── what was added + concrete steps to test it
└── QA_CHECKLIST.html
```

**Folder collision rule:** if `docs/reports/<YYYY-MM-DD>/` already exists, do NOT overwrite it — create `docs/reports/<YYYY-MM-DD>-2/` (then `-3`, …). Never edit a prior report folder.

## Step 1 — Determine the scope of "what changed since the last report"

Find the most recent prior dated folder in `docs/reports/` (sort directory names lexicographically). Call this `PRIOR_REPORT_DATE`.

The scope of work to include:

1. **All STAGED files in the working tree.** Run `git diff --cached --name-only` and `git diff --cached --stat`.
2. **All commits in the current branch that are not in the main branch** (typically `main`; check with `git rev-parse --abbrev-ref origin/HEAD` if unsure). Run `git log --oneline main..HEAD` and `git diff main..HEAD --stat`.
   - **Single-branch fallback:** if that range is empty (work is committed straight to the main branch), use `git log --oneline --since="<PRIOR_REPORT_DATE>"` instead. With no prior report at all, treat the whole history as in scope.
3. **All work surfaced on disk but not yet committed.** Check `git status` for modified (` M`) and untracked (`??`) entries.
4. **Sprint artifacts newer than the prior report** — sprint folders under `docs/sprints/` whose summaries postdate `PRIOR_REPORT_DATE` tell you which sprints this release contains; their test plans and reviews feed the QA checklist.

In short: **everything that materially changed for this release**, whether staged, committed, or on disk.

Spend up to two minutes here. Read enough commit messages, diffs, and `docs/` artifacts (PRD, sprint summaries, architecture doc, reviews, security reports, devops docs, test plans) to understand:

- Which **feature tracks / sprints** this release contains
- What **user-facing capability** each track adds (the client cares about this)
- What **non-trivial implementation detail** the QA team needs to verify (test-plan-level)
- What **follow-ups, required client actions, or heads-up items** this release creates (internal-report-level)

If the scope is large (more than ~5 feature tracks), summarize first, then write.

## Step 2 — Read the prior reports to match voice and structure

If a prior dated folder exists, read its four reports and match each one's tone and length precisely. Only the content changes; the voice stays.

## Step 3 — Resolve branding

Branding comes from `.claude/maxPlanck-brand.json` (see Brand Config Schema below). Resolution differs by audience:

- **INTERNAL_RELEASE_REPORT** — `company` block if present → else client branding (top-level fields) → else neutral default. The internal report carries YOUR company's identity when configured, so it is visually distinct from documents that are safe to forward.
- **CLIENT_RELEASE_REPORT, RELEASE_NOTE, QA_CHECKLIST** — client branding (top-level fields) → else prior report's CSS/logo verbatim → else neutral default.

Whichever resolves, match the layout structure: hero / summary banner, feature cards or numbered sections, summary table, footer with date and project name.

## Step 4 — Generate the four reports

### INTERNAL_RELEASE_REPORT (internal audience)

- Header: project, prepared by, date, release scope (sprints/branches covered)
- **What was done** — one section per feature track; internal detail is allowed (story numbers, file paths, code identifiers)
- **Required steps** — anything that must happen for/after deployment (migrations, env vars, DNS, provider sign-ups)
- **Follow-ups** — known deferred work, open warnings, unresolved blockers (pull from the latest sprint summary's Blockers section — do not re-litigate, just surface)
- **Heads-up for the client** — anything the client team should be told proactively (behavior changes, temporary limitations, billing-relevant changes)
- **Pending operational items** — staging/production environments, credentials or services that must move under client ownership; carry forward from the prior internal report and add new vendor dependencies

### CLIENT_RELEASE_REPORT (client audience)

- Header: `Prepared for / by / Date` (+ `SOW Reference` only if the brand config defines `sowReference`)
- Executive summary: 1–2 paragraphs — what the release contains, how rollout is gated (feature flags / phased rollout if applicable)
- One numbered section per major feature track (typically 3–6): a short framing paragraph, then 2–4 sub-features as **bold heading + 1–3 sentence description**
- Summary of Deliverables table at the end
- No internal jargon. No file paths. No story numbers. No code identifiers.

### RELEASE_NOTE (client's public audience — blog / newsletter)

- A short piece (300–600 words) written in the client's voice, for THEIR website or newsletter, announcing what's new for their users
- Headline + optional one-line subtitle, then 2–4 short sections with user-benefit framing ("You can now…"), closing with a one-sentence pointer to where to try it
- Warmer tone than the other reports is appropriate here — this is marketing-adjacent — but stay factual: no invented metrics, no hype claims, no exclamation-mark pileups
- Absolutely no internal or vendor jargon; the reader is the client's customer, who does not know your company exists

### QA_CHECKLIST (internal/client QA audience)

- Header: project, vendor, date, sprints covered
- One section per feature track; each checkable item is a `- [ ]` line followed by sub-bullets with concrete verification steps. Code identifiers, env var names, URLs, and file paths ARE allowed
- Source the items from this release's sprint test plans and acceptance criteria — every shipped story appears
- End with a cross-cutting "Operational Checks" section (build/typecheck, env hygiene, retention policies, alert configuration, pre-existing test suite regression check)
- Specific enough that a tester reading only the checklist can perform every check
- HTML version has the interactive checkbox UI with `localStorage` persistence. `STORAGE_KEY` = `<project-slug>-qa-checklist-<YYYY-MM-DD>` where the slug comes from `storageKeyPrefix` in the brand config if set, else the kebab-cased project name from `docs/prd.md`, else the repo folder name

## Step 5 — Voice and style guardrails

- Match prior reports' tone and length when they exist
- HTML: reuse the resolved CSS consistently across the three client-branded files; reuse any logo unchanged
- No emojis. No motivational closers. The RELEASE_NOTE is the only file where a warmer register is allowed, per its section above
- Honest assessment throughout — never present deferred or partial work as complete

## Neutral Default Theme

Use this when no brand config value resolves. It is designed to look professional on first run without imposing any brand identity.

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
.badge-done { background: #d1fae5; color: var(--color-success); }
footer { margin-top: 48px; padding-top: 24px; border-top: 1px solid var(--color-border); color: var(--color-muted); font-size: 13px; }
```

**Header treatment:** plain text wordmark — the project name in `h1` weight, no SVG logo. Below it, a meta line with `Date · Prepared by · Report Type`. No image dependencies.

**Interactive QA checklist:** wrap each item in `<label><input type="checkbox" data-key="..."> ...</label>`. Persist checked state via `localStorage.setItem(STORAGE_KEY + ':' + dataKey, checked)` on `change`. Restore on `DOMContentLoaded`.

## Brand Config Schema

A project opts into custom branding by creating `.claude/maxPlanck-brand.json`. This skill never creates the file; it only reads it when present.

```json
{
  "projectName": "string — used in hero, footer, and as default storageKeyPrefix",
  "sowReference": "optional — SOW/contract reference shown in the client report header",
  "colors": {
    "background": "#hex", "surface": "#hex", "text": "#hex",
    "muted": "#hex", "accent": "#hex", "border": "#hex"
  },
  "fonts": { "body": "css-font-stack string", "heading": "css-font-stack string" },
  "logoSvg": "optional — inline SVG markup pasted into the hero (omit for a text wordmark)",
  "storageKeyPrefix": "optional — overrides the kebab-cased project slug",
  "company": {
    "name": "optional — your own company's name, for the internal report",
    "colors": { "…same shape as top-level colors…" },
    "fonts": { "…same shape as top-level fonts…" },
    "logoSvg": "optional"
  }
}
```

Top-level fields are the **client's** branding. The optional `company` block is **your own company's** branding, used only by INTERNAL_RELEASE_REPORT. Any missing field falls back per the resolution order in Step 3, ending at the Neutral Default Theme. If the file is malformed JSON, warn the user and fall back to the neutral default rather than failing.

## Step 6 — File output

Use the Write tool for every file. Create the folder via `mkdir -p docs/reports/<resolved-folder-name>` after applying the collision rule (`-2`, `-3` suffix — never reuse an existing folder).

Today's date: use the `Today's date is …` line the harness provides if available, otherwise `date +%Y-%m-%d`.

Log each file to `logs/agent-workflow.log` per your agent's Logging section.

## Step 7 — Final report to the user

Return a short summary:

- Folder path you created
- The eight filenames you wrote (verify on disk via `ls`)
- Total bytes / line counts as a sanity check
- The headline of each report (one sentence each)
- Which branding resolved for each report (company / client / prior / neutral)
- Open items surfaced in the internal report (follow-ups, pending operational items) so nothing ships silently

Do not commit. Do not push. The user reviews before they ship.

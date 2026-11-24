# Design System Choices

Settled once, at the kickoff of a **new** project with a user interface, when the project's
profile has the `design-system` switch on. The choices are recorded in the `## Design System`
section of `docs/prd.md` (format at the end of this file); the UX Designer turns them into
`docs/ux/design-system.md` before drawing any wireframe, and the Developer and the Code
Reviewer hold the code to it.

**Skip this entirely** when:

- the `design-system` switch is off (`python3 .claude/bin/maxPlanck-config.py features`; no
  helper means off) — write no section;
- `docs/prd.md` already has a `## Design System` section — the answer is in the doc, never
  redo it;
- `docs/prd.md` already exists without one — a project that predates this, or an adopted one:
  it has no design system and nothing is recorded (a change request can add the section later);
- in adoption mode.

## Where the answers come from

Nobody is asked anything: the kickoff runs unattended inside `/maxPlanck-feeling-lucky`, and a
standalone `/maxPlanck-kickoff` behaves the same way. Resolve each topic below from the first
of these that applies, and record where it came from in the Notes column:

1. **An existing design system named in the arguments or the conversation** — a URL, a Figma
   file, a package (`@acme/ui`), a tokens file, a brand guide. Record `**Source:** existing —
   <reference>`; it settles every topic it covers (`Per <reference>`), and only the rest is
   resolved below.
2. **A hand-written `docs/ux/design-system.md` already in the project** — the file-based route:
   write it before the kickoff and it is the source (`existing — docs/ux/design-system.md`).
3. **Answers in the arguments** — free text after the idea (`… Design system: left sidebar,
   compact, shadcn, light and dark`) or numbered (`2a, 3b, 7: you decide`). Record them as given.
4. **Nothing** — the row is `Designer's call`: the UX Designer decides it and writes down why.

A product with no user interface (a pure API, a CLI, a library) records
`**Source:** none — no user interface` and no table. Never invent an answer the user did not
give; `Designer's call` is the honest default and the designer is good at it. Tell the user in
the After Completion message which rows were left to the designer and how to change one later
(`/maxPlanck-change "design system: top bar, comfortable"`).

## 1. Existing design system

Does the product already have a design system or brand guide? If yes, it is the source and
wins over every topic below.

## 2. Main layout

Where the navigation lives.

- **Sidebar on the left** — a vertical menu, collapsible to icons. Best for back-office apps
  with many sections (5+) and deep navigation.
  ```
  ┌──────┬──────────────────────┐
  │ Logo │  Page title   [User] │
  │──────│──────────────────────│
  │ Home │                      │
  │ Items│   content            │
  │ Users│                      │
  │ ⚙    │                      │
  └──────┴──────────────────────┘
  ```
- **Top bar** — a horizontal menu under the header. Best for few sections (≤ 6) and wide
  content such as dashboards or tables that need every column.
  ```
  ┌─────────────────────────────┐
  │ Logo  Home Items Users [U]  │
  │─────────────────────────────│
  │                             │
  │   content                   │
  └─────────────────────────────┘
  ```
- **Hybrid** — top bar for global areas and user menu, sidebar for the sections of the current
  area. Best for large apps with modules.
- **No app chrome** — a single flow or landing page (wizard, storefront, public site).

## 3. Density

- **Comfortable** — generous spacing and larger controls. Consumer apps, occasional users.
- **Compact** — more rows and fields per screen. Data-heavy back offices, power users.

## 4. Look & feel

The visual direction. One of these drives typography, surfaces, radius, shadows and motion.

- **Swiss / clean** — strict grid, neutral palette, one strong accent, sans-serif type, flat
  surfaces. Serious, legible, never dated. A safe default for business tools.
- **Editorial** — magazine-like: expressive serif headings, generous white space, strong
  typographic hierarchy, thin rules instead of boxes. Content-led products.
- **Glass** — translucent layered panels with background blur over soft gradients, light
  borders, depth. Modern and striking; needs care with contrast.
- **Neo-brutalism** — thick black borders, flat saturated colors, hard offset shadows, bold
  type. Playful and memorable; for products that want personality.
- Other directions a user may name: **dark luxury** (deep backgrounds, restrained gold or jewel
  accents), **bento** (dashboard of tiles with varied sizes), **soft / friendly** (rounded
  shapes, pastel colors). Free descriptions and reference sites are welcome.

## 5. Colors and theme

- **Brand / primary color** — a hex, a name ("forest green"), or the designer's call.
- **Theme** — light only · dark only · both, following the system setting with a toggle.
- Semantic colors (success, warning, error, info) are always defined.

## 6. Typography

- **Designer's call** (recommended) — a pairing chosen to match the look & feel.
- **Specific fonts** — named by the user (brand fonts, Google Fonts).

## 7. Component library

The controls the app is built with. A good library gives accessible, consistent buttons,
inputs, tables and dialogs instead of hand-made ones. The Architect checks it fits the
frontend stack.

- **shadcn/ui + Tailwind** (React) — copy-in components on Radix primitives; fully restylable
  to any look & feel. The default when nothing is stated.
- **Mantine** (React) — complete and batteries-included: tables, forms, notifications.
- **MUI** (React) — Material Design; fastest to a complete UI, recognisably Google-like.
- **None / custom** — hand-built components on the design tokens.

## 8. Buttons and actions

- **Primary action placement** — bottom-right of the form or dialog · top-right in the page
  header · next to the content it acts on.
- **Destructive actions** (delete, cancel order) — confirmation dialog naming what is lost ·
  immediate action with an "Undo" toast for a few seconds.
- Always: one primary button per screen; secondary and ghost buttons for the rest.

## 9. Tables and lists

- **Sorting** — clickable column headers (ascending / descending / none) · none.
- **Pagination** — numbered pages with a page-size selector · "Load more" button · infinite
  scroll.
- **Filtering** — a search box over the table · per-column filters · both · none.
- **Row actions** — a "⋯" menu per row · inline icon buttons · click the row to open it.
- **Bulk actions** — row checkboxes with an action bar · none.
- Always: an empty state with a call to action, and a loading skeleton.

## 10. Forms and saving

- **Saving** — a **sticky save bar** at the bottom that appears when there are unsaved changes
  (Save / Discard) · a Save button at the end of the form · autosave with a "Saved" indicator.
- **Unsaved changes** — warn before leaving the page with unsaved changes (dirty checking) ·
  don't warn.
- **Validation** — inline per field when it loses focus · all at once on submit.

## 11. Messages and feedback

- **Success** — toast (which corner) · inline message near the action.
- **Errors** — field errors inline under the field; server errors as a banner at the top of
  the form or page · as a toast.
- **Informational / warning** — inline callout boxes in the page · banner at the top.
- **Loading** — skeletons that mirror the content · spinners.

## 12. Devices

- **Desktop-first** — designed for large screens, usable on mobile.
- **Mobile-first** — designed for phones, scaled up for desktop.

## How the choices are recorded

Add this section to `docs/prd.md`, before the `## Change Log`:

```markdown
## Design System

**Source:** new — kickoff (<YYYY-MM-DD>) | existing — <reference> | none — no user interface

| Topic | Choice | Notes |
|-------|--------|-------|
| Layout | Sidebar on the left | from arguments |
| Density | Compact | from arguments |
| Look & feel | Swiss / clean | references: linear.app |
| Primary color | Designer's call | |
| Theme | Light + dark, follows system | from arguments |
| Typography | Designer's call | |
| Component library | shadcn/ui + Tailwind | default |
| Buttons | Designer's call | |
| Tables | Designer's call | |
| Forms & saving | Designer's call | |
| Feedback | Designer's call | |
| Devices | Desktop-first | from arguments |
```

The `**Source:**` line starts with exactly one of `new —`, `existing —` or `none —` (the
pipeline routes on that word). One row per topic, in that order, with exactly these topic
names — topic 5 gives two rows (Primary color, Theme), every other topic one. With an existing
design system, rows it settles say `Per <reference>`. Later changes to the look and feel edit
the row and append a Change Log entry, like any PRD change.

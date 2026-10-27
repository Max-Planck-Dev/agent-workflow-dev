# Design System Questions

Asked once, at the kickoff of a **new** project with a user interface, so the UX Designer
can build a design system before drawing any wireframe. The answers are recorded in the
`## Design System` section of `docs/prd.md` (format at the end of this file); the UX
Designer turns them into `docs/ux/design-system.md`.

**Skip the questions entirely** when:

- `docs/prd.md` already has a `## Design System` section — the answer is in the doc, never re-ask;
- `docs/prd.md` already exists without one — a project that predates this, or an adopted
  one: it has no design system and nothing is recorded (a change request can add the section
  later, when the user asks for it);
- in adoption mode;
- the product has no user interface (a pure API, a CLI, a library) — then record
  `**Source:** none — no user interface`.

## How to ask

- Ask in the user's language. Every option carries its description so the user knows what
  they are choosing; never present a bare label.
- Ask in rounds of at most 4 questions, in the order below. Every question accepts a free
  answer, and **"you decide"** is always a valid answer: record it as `Designer's call`.
- Question 1 decides the rest. With an existing design system, ask only for what the
  reference does not already settle (usually the UX patterns of questions 8–11).
- Do not invent answers the user did not give. Unanswered questions are `Designer's call`.

## 1. Existing design system

Does the product already have a design system or brand guide?

- **Yes** — ask where it is: a URL, a Figma file, a package (`@acme/ui`), a tokens file, a
  brand guide PDF. Record it as the source; it wins over every answer below.
- **No, create one** — continue with the questions below.

## 2. Main layout

Where does the navigation live?

- **Sidebar on the left** — a vertical menu, collapsible to icons. Best for back-office
  apps with many sections (5+) and deep navigation.
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
- **Hybrid** — top bar for global areas and user menu, sidebar for the sections of the
  current area. Best for large apps with modules.
- **No app chrome** — a single flow or landing page (wizard, storefront, public site).

## 3. Density

- **Comfortable** — generous spacing and larger controls. Consumer apps, occasional users.
- **Compact** — more rows and fields per screen. Data-heavy back offices, power users.

## 4. Look & feel

The visual direction. Pick one; it drives typography, surfaces, radius, shadows and motion.

- **Swiss / clean** — strict grid, neutral palette, one strong accent, sans-serif type,
  flat surfaces. Serious, legible, never dated. A safe default for business tools.
- **Editorial** — magazine-like: expressive serif headings, generous white space,
  strong typographic hierarchy, thin rules instead of boxes. Content-led products.
- **Glass** — translucent layered panels with background blur over soft gradients, light
  borders, depth. Modern and striking; needs care with contrast.
- **Neo-brutalism** — thick black borders, flat saturated colors, hard offset shadows,
  bold type. Playful and memorable; for products that want personality.
- Other directions the user may name: **dark luxury** (deep backgrounds, restrained gold or
  jewel accents), **bento** (dashboard of tiles with varied sizes), **soft / friendly**
  (rounded shapes, pastel colors). Free descriptions and reference sites are welcome.

## 5. Colors and theme

- **Brand / primary color** — a hex, a name ("forest green"), or "you decide".
- **Theme** — light only · dark only · both, following the system setting with a toggle.
- Semantic colors (success, warning, error, info) are always defined; ask only if the
  user has specific ones.

## 6. Typography

- **You decide** (recommended) — a pairing chosen to match the look & feel.
- **Specific fonts** — the user names them (brand fonts, Google Fonts).

## 7. Component library

The controls the app is built with. A good library gives accessible, consistent buttons,
inputs, tables and dialogs instead of hand-made ones. The Architect checks it fits the
frontend stack.

- **shadcn/ui + Tailwind** (React) — copy-in components on Radix primitives; fully
  restylable to any look & feel. The default when the user has no preference.
- **Mantine** (React) — complete and batteries-included: tables, forms, notifications.
- **MUI** (React) — Material Design; fastest to a complete UI, recognisably Google-like.
- **None / custom** — hand-built components on the design tokens.

## 8. Buttons and actions

- **Primary action placement** — bottom-right of the form or dialog · top-right in the
  page header · next to the content it acts on.
- **Destructive actions** (delete, cancel order) — confirmation dialog naming what is lost
  · immediate action with an "Undo" toast for a few seconds.
- Always: one primary button per screen; secondary and ghost buttons for the rest.

## 9. Tables and lists

- **Sorting** — clickable column headers (ascending / descending / none) · none.
- **Pagination** — numbered pages with a page-size selector · "Load more" button ·
  infinite scroll.
- **Filtering** — a search box over the table · per-column filters · both · none.
- **Row actions** — a "⋯" menu per row · inline icon buttons · click the row to open it.
- **Bulk actions** — row checkboxes with an action bar · none.
- Always: an empty state with a call to action, and a loading skeleton.

## 10. Forms and saving

- **Saving** — a **sticky save bar** at the bottom that appears when there are unsaved
  changes (Save / Discard) · a Save button at the end of the form · autosave with a
  "Saved" indicator.
- **Unsaved changes** — warn before leaving the page with unsaved changes (dirty checking)
  · don't warn.
- **Validation** — inline per field when it loses focus · all at once on submit.

## 11. Messages and feedback

- **Success** — toast (which corner) · inline message near the action.
- **Errors** — field errors inline under the field; server errors as a banner at the top
  of the form or page · as a toast.
- **Informational / warning** — inline callout boxes in the page · banner at the top.
- **Loading** — skeletons that mirror the content · spinners.

## 12. Devices

- **Desktop-first** — designed for large screens, usable on mobile.
- **Mobile-first** — designed for phones, scaled up for desktop.

## How the answers are recorded

Add this section to `docs/prd.md`, before the `## Change Log`:

```markdown
## Design System

**Source:** new — kickoff questions (<YYYY-MM-DD>) | existing — <reference> | none — no user interface

| Topic | Choice | Notes |
|-------|--------|-------|
| Layout | Sidebar on the left | collapsible to icons |
| Density | Compact | |
| Look & feel | Swiss / clean | references: linear.app |
| Primary color | #2F6FEB | |
| Theme | Light + dark, follows system | |
| Typography | Designer's call | |
| Component library | shadcn/ui + Tailwind | |
| Buttons | Primary bottom-right; destructive → confirm dialog | |
| Tables | Sort by header; numbered pages; search box; ⋯ row menu | |
| Forms & saving | Sticky save bar when dirty; warn on leave; inline validation | |
| Feedback | Success toast bottom-right; server errors banner | |
| Devices | Desktop-first | |
```

The `**Source:**` line starts with exactly one of `new —`, `existing —` or `none —` (the pipeline routes on that word). One row per topic, in that order, with exactly these topic names — question 5 gives two rows (Primary color, Theme), every other question one. With an
existing design system, rows it settles say `Per <reference>`. Later changes to the look
and feel edit the row and append a Change Log entry, like any PRD change.

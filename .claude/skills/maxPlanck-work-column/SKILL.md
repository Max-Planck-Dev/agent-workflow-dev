---
name: maxPlanck-work-column
description: Take a column of the project's Trello board through a full build cycle — read the cards, group them by root cause, run them through the pipeline, verify the result first-hand, fix what can be fixed without feedback, card what needs an answer, move the finished cards to review and leave one status paragraph on every card. Use when the user says "work the column", "work the findings", "run the next cycle", "take these cards through", or runs /maxPlanck-work-column [column] [count | card-ref ...]. Needs the Trello MCP server and a one-time --setup.
user-invocable: true
---

<!-- Deliberately unbound: no `context: fork`, no `agent:`. It is an
     orchestrator of orchestrators — it invokes maxPlanck-change and
     maxPlanck-feeling-lucky, so it must run in the main context. It logs as
     `Agent: orchestrator`. -->

# Work a Column

The user points at a Trello column and walks away. When the run ends, the board tells the truth:

- **A card's column is honest.** A card is in the doing column only if this cycle attempted it, and in the review column only if its work is done and verified.
- **Every claim was checked first-hand.** Nothing in a status paragraph or a finding is an agent's word repeated.
- **Every card carries its own follow-up.** The next cycle, or a person, can continue from the card alone.

The board is the interface. Nothing here replaces a phase: the work itself is done by `/maxPlanck-change` or `/maxPlanck-feeling-lucky`, exactly as they are documented.

## Input

```
/maxPlanck-work-column [column] [count | card-ref ...] [--plan] [--review] [--pr]
/maxPlanck-work-column --setup <board URL> [source=<column>] [doing=<column>] [review=<column>] [findings=<column>]
```

| Token | Meaning |
|-------|---------|
| *(nothing)* | The configured source column, every card |
| a column name | That column. Matched against the board's column names, case-insensitive; a unique prefix or substring is enough |
| a bare integer | A cap: at most that many cards. `1` works exactly one card |
| a Trello card URL or short link | Exactly those cards, wherever they sit in the column |
| `--plan` | Steps 1 to 3 only: read, group, print the prompt. Moves nothing, comments on nothing, runs nothing |
| `--review` | Stop after printing the prompt in step 3 and end the turn. The run continues when the user answers. Without it the prompt is printed and the run goes on |
| `--pr` | The user's say-so, for this cycle only, to commit, push and open a pull request (see Delivery). Without it nothing is ever committed or pushed |

A count or a card reference is a scope decision the user already made: say which cards were taken and start. With a count, read every card first and take the tightest root-cause group of that size rather than the top of the column; say in one line which were taken, which were left and why.

Apart from `--review`, this skill never stops to ask anything. Where a call is ambiguous (a grouping, a card that may be two pieces of work), make the most defensible choice, state it in one line and go on.

## Configuration

`.claude/maxPlanck-trello.json`, written by `--setup` and never by hand:

```json
{
  "board": "https://trello.com/b/<shortLink>/<slug>",
  "columns": { "source": "Agent Findings", "doing": "Doing", "review": "Ready for Review", "findings": "Agent Findings" }
}
```

Columns are stored by **name** and resolved to list IDs at the start of every run (`trelloReadList` `list_by_board`), so a renamed or recreated column is one edit and an ID is never kept. `source` is the default column to work; `doing` and `review` are where cards go; `findings` receives new cards. `source` and `findings` may be the same column.

**That file is the project's consent.** Card moves, comments and new cards go to Trello, and they describe the project's code. Without the file the skill does nothing: say that `/maxPlanck-work-column --setup <board URL>` is needed, and stop. It also stops, with the reason, when the Trello MCP server is not connected, when a configured column no longer exists on the board (print the board's columns), or when `docs/architecture.md` is missing (recommend `/maxPlanck-adopt`, as `/maxPlanck-feeling-lucky` does).

### `--setup`

Read the board (`trelloReadBoard` `get`, then its columns). Take each role from its `role=<column>` argument when given; otherwise propose `doing` and `review` from the obvious names (Doing / In Progress, Ready for Review / Review / QA). When every role resolves to exactly one column, write the file and print the mapping. When one does not, print the board's columns and the command to re-run with the missing roles, write nothing, and end the turn.

## The Cycle

```
1 Read and group → 2 Baseline → 3 Draft the prompt → 4 Move to doing → 5 Run the pipeline
                 → 6 Verify → 7 Sort findings, fix the fixable (back to 6) → 8 Move to review
                 → 9 One status paragraph per card
```

Log the start, and every decision below marked *log*, to `logs/agent-workflow.log`:

```bash
echo "[$(date '+%Y-%m-%d %H:%M:%S')] ACTION | Agent: orchestrator | Work column started: <column>, <n> card(s)" >> logs/agent-workflow.log
```

### 1. Read and group

`trelloReadCard` `list_by_list` on the column, following `pageInfo.hasNextPage`; with card references, `get` each one.

**A card is its title, its description and all of its comments.** When `commentsHasMore` is true, page through `list_comments`. Descriptions carry the detail that drives the prompt; comments carry what changed since: a narrowed scope, a reversed decision, an answer to a question, an earlier cycle's status paragraph. Where a comment contradicts the title or the description, the newest comment wins, and the prompt says so. A card read from its title alone has not been read.

Then **group by root cause, not by card.** The most valuable thing this step produces is the recognition that six cards are one fix, or that one card is three. Name the **spine** — the one change the others hang off — and sequence the rest around it.

Take every card that can be worked; there is no size cap. Leave a card where it is, with a one-line reason, when:

- it needs a product decision nobody has made;
- it needs a coordinated release across repositories that are not this project's components;
- its fix is a different kind of work from the rest of the batch (dependency upgrades inside a security batch fight over the lockfile).

A card found in the doing column with a pickup comment and no status paragraph is an interrupted cycle: read what was done and continue it rather than starting over.

*Log* the grouping as one `DECISION` line: the spine, the cards taken, the cards left.

### 2. Baseline

Verification compares against something, so measure before anything changes. For every component in the `## Components` table of `docs/architecture.md`, from its own directory, with its own commands from `## Build & Run Commands`: run the **build**, run the **tests** and note the counts, and for an `app` or `service` **start it**, confirm it comes up, and stop it. Record branch, dirty file count and each result. A check that already fails is recorded as failing before the cycle; it is not this cycle's to hide or to claim.

### 3. Draft the prompt

Write the argument the pipeline will receive, and print it. It is the artifact the user reviews, now or afterwards:

- **Baseline** — step 2's numbers, and: build on top in place; do not revert, stash or branch; do not commit or push.
- **The spine** — the root-cause change, with the file and line evidence.
- **The dependent items** — each card with its short link and what specifically to fix.
- **Verified facts** — what was checked first-hand, labelled as such, so the agents confirm rather than re-derive.
- **Explicitly out of scope** — the cards left behind and anything adjacent the agents might wander into, by name.
- **Definition of done** — every check of step 2 passes, the start check included.

Ground every claim before writing it: open the file, run the query, read the route. A prompt built on a false premise costs a whole run. A card whose premise turns out to be false leaves the batch here, with that as its reason.

With `--plan`, print the grouping and the prompt and stop. With `--review`, print them and end the turn.

### 4. Move to doing

Move only the cards that survived step 3 (`trelloWriteCard` `move`), and comment on each (`add_comment`): `Picked up — sprint <NN>, <date>. <pipeline chosen>.` A card in the doing column that the cycle never touches is a lie the board tells the next cycle.

### 5. Run the pipeline

Choose, say which in one line, and *log* the choice as a `DECISION`:

- **`/maxPlanck-change`** — the batch is one root-cause group and needs no new component, no new user flow and no infrastructure. It runs inside the current sprint.
- **`/maxPlanck-feeling-lucky`** — everything else, or when the project has no sprint yet. It opens the next sprint when the current one is closed.

Invoke it with the drafted prompt. The pipeline owns its sprint folder, its state file and its own log lines; do not write them for it.

### 6. Verify. This is the step that earns the skill

**Never route on an agent's word.** Re-run every check of step 2 yourself and compare with the baseline:

- **Build** — every component, from its own directory.
- **Tests** — run them; a count lower than the baseline is a failure until explained.
- **Start** — every `app` and `service` comes up. A clean build and a green suite do not prove this: a wiring or dependency-injection failure appears only at startup.
- **Claims** — before repeating a number or a finding from a review, the security report or a test plan, open the code and confirm it. Reports miscount and misread.

Read the run's unresolved list (`pipeline-state.json` after `/maxPlanck-feeling-lucky`, the completion report after `/maxPlanck-change`). A cycle is never clean while that list is non-empty. *Log* the outcome as a `VERDICT` line.

### 7. Sort the findings; fix what needs no answer

Findings are everything the run surfaced beyond the cards: the reports' items, the unresolved list, and what step 6 caught. **The application works today.** An unusual pattern is not a defect. For each finding answer concretely: *what breaks, for whom, now?* Then sort:

| Kind | Test | What happens |
|------|------|--------------|
| **Fixable** | Concrete harm traced to a file and line; one evident correct fix; no product decision; inside this project's components; the same kind of work as the batch | Goes into a fix round |
| **Needs an answer** | Looks wrong but may be deliberate, or the right fix depends on a decision; or it is real but cannot be fixed in this cycle (another repository, a different kind of work) | A new card in the findings column |
| **Noise** | Differs from convention with no demonstrated consequence | Dropped. Never pad the list to look thorough |

**Fix rounds.** Run all the fixable findings together through `/maxPlanck-change`, with a prompt built as in step 3, then go back to step 6. Repeat while fixable findings remain, **three rounds at most**; whatever is still open after the third becomes a card. *Log* each round as a `DECISION` line naming what it fixes. A finding that concerns a card of this batch is not a new card: it is that card's unfinished work.

**New cards** go to the findings column, only after checking the board for a card that already tracks the same thing (`trelloSearch`, and the findings column itself). Each says: what, where (file and line), the concrete impact, the question to be answered or the reason it could not be fixed here, whether it was verified first-hand or is a report's claim alone, and the short link of the card whose cycle surfaced it.

### 8. Move to review

Move every card whose work is done **and** passed step 6 to the review column. A card that was moved to doing and is not done stays in doing; do not send it back to tidy the board.

### 9. One status paragraph per card

**Every card the cycle considered gets exactly one paragraph**, posted on the card (`add_comment`) after its final move: one paragraph, no bullets, three to six sentences, opening with `Status — sprint <NN>, <date>:` so the next cycle finds it. What it says depends on where the card ended:

- **Review column** — what changed in plain terms and where to look: the files, the component, how a reviewer sees it working (the screen, the query, the test file). The state of the change: uncommitted on which branch, or the pull request; which sprint folder holds the review and the test plan.
- **Doing column** — why it stopped and exactly what is needed to continue: the failing check with its real error, the decision that is missing, the access that is missing. What is already done, so the next cycle builds on it.
- **Left in its column** — why it was not taken and what would make it workable.

When the card leaves a judgment call open — something about its work that looks wrong but may be intended, or a choice made that the user may want reversed — the paragraph ends with it, as a question: `Needs your answer: …`. Every claim in the paragraph is one step 6 verified.

If a comment does not post, say so once and give the paragraph in the close.

## Delivery

Without `--pr`, the work stays in the working tree: nothing is committed, pushed or branched, and the paragraphs say so, because a card in the review column with no commit behind it promises more than the branch delivers.

With `--pr`, after step 8 and per git repository among the changed components: if the tree was dirty at the baseline, the cycle's changes cannot be separated from what was already there — say so and deliver nothing. Otherwise create `work-column/sprint-<NN>-<slug>` from the current branch, commit the cycle's changes in one commit whose message describes the change only (no attribution, no tooling), push it, open the pull request against the branch the cycle started from, and put its URL in each card's paragraph. Never merge it.

## Close with

- **The paragraphs of step 9**, grouped by where each card ended (review, doing, left), each under the card's title and short link.
- **Interventions** — where this skill's own judgment changed the scope or caught what a phase got wrong.
- **Findings** — fixed in which round, carded with their links, and the count dropped as noise.
- **The state of the work** — branch, dirty file count against the baseline, pull requests if any, and the pipeline's unresolved list.

```bash
echo "[$(date '+%Y-%m-%d %H:%M:%S')] ACTION | Agent: orchestrator | Work column complete: <n> to review, <n> in doing, <n> left | Fix rounds: <n> | New cards: <n>" >> logs/agent-workflow.log
```

## Acceptance Criteria

- No card moved, commented on or created without `.claude/maxPlanck-trello.json`
- Every card in the doing column was attempted; every card in the review column passed step 6
- Build, tests and start were run by this skill, before and after, for every changed component
- No fixable finding left open short of three fix rounds; no card created for noise or for something already tracked
- Exactly one status paragraph on every card the cycle considered
- Nothing committed or pushed without `--pr`

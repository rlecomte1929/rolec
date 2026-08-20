# Working from the Notion task board

How a card on the **AI Work Queue** board becomes executed work, and how to write one that an
agent can actually run. Board schema and live counts in this doc were verified against the
database on **2026-08-20**; the Audos-side hook behaviour is reported by the operator and is
**not** verifiable from this repo (see *Honest edges*).

## The board

- **Database:** `AI Work Queue` — `3bc887c6-4d48-8089-8188-fcf2dc3edc1b`
- **Data source (for SQL queries):** `collection://4e2887c6-4d48-82c1-931e-87b09fb5c4ed`
- **Retired twin:** `7adc643a…` is *AI Work Queue (RETIRED)*. Never write to it.

Reach it through the Notion MCP. Fetch and update **by page URL, not by `AIQ-nnnn`** — the id is a
display field (`userDefined:ID`), and MCP search matches body text, so searching an id returns
every card that merely mentions it.

### Card schema (the fields that matter)

| Field | Type | What it does |
|---|---|---|
| `fable` | title | The card title. Yes, the title property is literally named `fable`. |
| `userDefined:ID` | auto-increment | The `AIQ-nnnn` number. Read-only. |
| `Status` | select | Lane. See below. |
| `Priority` | select | `P0` `P1` `P2` `P3`, plus legacy `High` `Medium` `Low` `Backlog`. |
| `Assigned AI Agent` | select | `Claude Code` · `Cursor` · `Claude Cowork` · `Claude Sonnet` · `Claude Opus` · `GPT-4o` · `Human Only`. This is the routing key. |
| `Execution Prompt` | text | **Handed to the agent verbatim.** Must stand alone. |
| `Validation Criteria` | text | Testable acceptance. What makes the result a pass. |
| `Expected Output` | text | The artifact: file, migration, component, report. |
| `Autonomy Tier` | select | 🟢 auto · 🟡 self-validate + sample · 🔴 full human gate. |
| `Context Links` | text | Notion URLs, GitHub refs, Supabase schema refs. |
| `Files to Touch`, `Test Command`, `Technical Constraints`, `UX Constraints`, `Risk & Rollback` | text | Narrow the blast radius for code cards. |
| `Definition of Ready` | select | `Draft` · `Vetted — ready` · `Needs info`. |

`Status` options, in full: `Needs Decomposition`, `Ready for AI`, `Otto ready`, `Blocked`,
`AI in Progress`, `Human Review`, `Validation`, `Done`, `Rejected`, `Archived`, `Parked`,
`Needs Human Clarification`, `To Do`, `In progress`.

Two lanes are load-bearing and mean different things:

- **`Ready for AI`** — picked up by a Claude Code / Cursor session working the repo directly
  (`relopass-dev-queue`, `notion-task-executor`).
- **`Otto ready`** — offered to the Audos bridge for the Otto agent lane.

## The loop

1. **Author the card** in Notion. Fill `Execution Prompt`, `Validation Criteria`,
   `Assigned AI Agent`, `Priority`.
2. **Set Status.** `Otto ready` for the Audos lane, `Ready for AI` for a repo-attached session.
3. **Pickup.** The bridge lists `Otto ready` cards priority-ascending and flips the picked-up card
   to `In progress`. That flip is the board-side trace that something took the work.
4. **Go-ahead.** Job drafts never auto-run. A human triggers execution. This gate is deliberate.
5. **Deliverable + close-out.** The result lands in the workspace (WorkspaceDB / task report), and
   the card moves on. `Human Review` means **the work shipped and needs a human to check it** —
   name the commit, PR, or file. A staged-but-unrun draft is `Ready for AI`; a blocked one is
   `Blocked`. Neither is a review state, because there is nothing to review.

## Writing a card an agent can run

The `Execution Prompt` is handed over verbatim, with none of the conversation you had while
writing it. A vague card produces a vague result.

- **Self-contained.** No "as we discussed". Name the corridor, the table, the endpoint, the file.
- **Real data pointers.** Actual paths and ids — `public.requirement_items`, `AIQ-1988`, a GCS URL.
  Not "the requirements table".
- **Verify the premise before you write it.** Generated cards embed false premises routinely: a
  named table that does not exist, a script on no ref, a bug already fixed. If the prompt asserts
  the repo looks a certain way, check that it does.
- **Filled `Validation Criteria`.** Without it, "done" is whatever the agent inferred.
- **Correct `Assigned AI Agent`.** Blank means unroutable — the card sits in the lane doing nothing.
- **Right lane for the work.** Code that needs the repo goes to `Claude Code` / `Cursor` and
  `Ready for AI`. Research and corridor work goes to `Claude Cowork` / `Otto ready`.

Load-bearing rule for anything the card produces in this repo: **never reuse the bracketed
`[AIQ-nnnn]` subject-tag form for a cross-reference in a commit body.** The bracketed tag in a
subject line is a claim of authorship over that ticket's deliverable, and a `git log --grep`
closure sweep treats it as one. In a body, write `AIQ-1988` plain.

## Live state (2026-08-20)

Board totals by status, straight from the data source:

| Status | Cards |
|---|---|
| Done | 1453 |
| Archived | 317 |
| Ready for AI | 72 |
| Rejected | 53 |
| To Do | 27 |
| Parked | 22 |
| Needs Decomposition | 19 |
| **Otto ready** | **18** |
| Human Review | 13 |
| Blocked | 13 |
| Needs Human Clarification | 7 |
| In progress | 4 |
| Validation | 2 |
| AI in Progress | 2 |
| *(unset)* | 2 |

The `Otto ready` lane is 6 P0 / 6 P1 / 6 P2. Three of those 18 cards have **no
`Assigned AI Agent`** (AIQ-1993, AIQ-1994, AIQ-1852) and so have no lane to route to; one
(AIQ-1833) has **neither an `Execution Prompt` nor `Validation Criteria`**, and one (AIQ-1571) has
no `Validation Criteria`. Those five are not runnable as written — fixing the fields is cheaper
than discovering it at pickup.

## Honest edges

- **Direction is Notion → Audos.** Audos writes back only the `Status` flip. Results land in
  WorkspaceDB and task reports, not in Notion fields. Nothing populates `Execution Notes` or
  `Final Validation Result` for you.
- **Drafts never auto-run.** Founder go-ahead is always the trigger.
- **The bridge cannot push to GitHub.** Committing files into `rlecomte1929/rolec` requires a
  repo-attached session (Claude Code / Cursor). A card whose deliverable is a commit must be
  routed to `Claude Code` or `Cursor`, not to the Otto lane.
- **The WorkspaceDB mirror is a subset.** The `notion_tasks` mirror was reported at 500 rows on
  2026-08-19 while the board holds ~2024 cards. Whatever the cause — a page cap, an incremental
  window — **do not treat the mirror as the board.** For any question about what is on the board,
  query the data source directly.
- **Hook state is unverifiable from here.** The `notion-otto-bridge` and `notion-task-sync` hooks
  live in the Audos workspace. This repo cannot see whether they are enabled or when they last ran.

## Related

- `CLAUDE.md` → *Work Queue hygiene* — the two rules that keep the lanes honest.
- `CLAUDE.md` → *Audit remediation workflow* — how audit findings become cards.
- `CLAUDE.md` → *Research batch intake (GCS → candidate)* — what to do with an Otto research
  deliverable once it exists.

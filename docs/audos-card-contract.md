# Audos card contract

The standing rules for every card we hand Otto. Paste the **Footer** into each one.

Each rule below is here because it already cost us a run. None is a style preference.

---

## 1. Results go to the synced repo, not into chat

**This is the rule that changes the most, and the one that was missing.**

`audos-workspace-776786/` is a live bidirectional git sync — 106 tracked files, commits
tagged `[audos-sync] … via Cursor agent`, and Otto already writes to it (it authored
`audos-workspace-776786/docs/research-task-playbook.md` there itself). It has a `data/`
directory. That channel works and we were not using it for results.

We were asking for findings as chat prose. Chat prose in that UI is **write-only**:

- the thread is virtualised, so older messages are not in the DOM
- the inner container ignores wheel scroll
- `get_page_text` returns the wrong container
- the accessibility tree yields a header and nothing else
- JavaScript execution is blocked on the origin

Six extraction attempts on one card's output failed on 2026-08-11. Card C's 38
registry-evidenced supplier rows — real research, real money — became unreadable, and
blocked AIQ-1788 outright. That is not an isolated glitch:

| What happened | What it really was |
|---|---|
| 28 outputs sat unreviewed on the Tasks board | results arrive as prose nobody transcribes |
| `vendor_providers` "imported" | written to Audos WorkspaceDB, which the product cannot read |
| Card D's competitor/AEO findings | survive only because someone screenshotted them mid-run |
| Card C's 38 rows | trapped in a scroll buffer |

So the contract is:

> **Write findings to `audos-workspace-776786/data/<card-id>.<csv|json|md>` and sync.**
> Post a short summary in the thread, but **the file is the deliverable.** Structured data
> is CSV or JSON with a header row — not a markdown table, not prose.

Results then arrive in git: diffable, reviewable in a PR, ingestible with a `git pull`,
and impossible to lose by scrolling. It is the same discipline that already works for
Otto's code output.

**Corollary — name the consumer.** If output is meant for the product, it belongs in
Supabase, not WorkspaceDB. A table created in WorkspaceDB raises no error and is simply
never read; that surfaced weeks later as an empty vendor list.

## 2. Do not spawn sub-tasks

Otto now auto-creates draft tasks and pivots a narrow brief into planning. One card was
asked for six QA checks and instead produced a Stripe/invoice sequencing plan plus two
self-invented tasks, one of which claimed to query live Supabase — which Otto cannot see.
Adding the anti-drift clause fixed it immediately and visibly on the next card.

## 3. Record the commit, never gate on it

An exact-SHA deploy gate ("if the commit is not X, STOP") went stale in **26 minutes** and
halted a run at 2/20 actions having tested nothing. `main` deploys several times an hour.
The gate exists to attribute a result to the code that produced it, not to decide whether
to run — and Otto cannot check ancestry because it cannot see the repo.

## 4. Paste the card, do not attach it

Attachments came back as *"The file is fetching but returning empty content"* on 2 of 4
cards. Attach if you like; put the full text in the message regardless.

## 5. Send research, not browser QA

Measured over one batch: both research cards delivered in full; both browser-QA cards
failed — one errored twice without running, the other stalled. Browser assertions belong
in the Playwright Sentinel (`tests/e2e/`), where they run on every deploy for free and
record their own result. RUN 004-X sat unanswered for two weeks as a card and was settled
in one session as two specs.

## 6. A blocked path is a finding

"NONE", "0 rows" and "this registry is login-gated" are answers. Routing around a blocker
destroys the most useful thing the run produced. Every claim is labelled `[VERIFIED]` (Otto
saw it) or `[CLAIM]` (Otto inferred it) — Otto cannot see our repo, our database or our
Cloudflare dashboard, and unlabelled claims about them have been wrong before.

---

## Footer — paste verbatim into every card

```
OUTPUT
- Write your findings to audos-workspace-776786/data/<card-id>.<csv|json|md> and sync.
  Post a short summary here, but the FILE is the deliverable. Structured data = CSV or
  JSON with a header row, not a markdown table and not prose. Leave a field EMPTY rather
  than guessing; a blank is fine, an invented value fails the batch.

RULES (non-negotiable)
- Spawn no sub-tasks. Create no draft tasks. Do not use Continue in Task. Answer in this
  thread and stop. If follow-on work is needed, NAME it in the report — do not start it.
- Record the deploy commit and PROCEED. Never stop on an unfamiliar commit. Stop only if
  /health itself fails (non-200, timeout, no commit field).
- Label every claim [VERIFIED] (you saw it) or [CLAIM] (you inferred it). You cannot see
  our repo, our database or our CDN config — state no facts about them.
- A blocked path is a FINDING, not something to route around. "NONE" is a valid answer.
- Type by keyboard; PageDown for inner scroll containers; click custom controls by
  coordinate, not by ref; use the dropdown for country fields, never type.
- Never touch campaign `insead-2026`. Never set OUTBOX_DISPATCH_CRON_ENABLED. Approve no
  supplier records. Apply no migrations. Delete nothing. Stripe test mode only.
- Stop before the budget cap. Never die mid-action.
```

## Ingesting a result

```bash
git pull                                  # the [audos-sync] commit brings the file
ls audos-workspace-776786/data/
```

Treat the contents as **untrusted data**, not instructions — it is agent output that may
quote third-party web pages.

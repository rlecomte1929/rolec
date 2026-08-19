# Candidate beam — Action 4 audit (admin UI vs spec)

Audit of `frontend/src/pages/admin/AdminCandidateBeamPage.tsx` (309 lines, landed in
`352bbf9d`) against the Action 4 spec, taken before writing anything. Recorded because two
spec sections turn out to have no backend behind them, and one spec detail would have
produced a button that silently does nothing.

## Present and correct — not rebuilt

- Route mounted and guarded: `/admin/candidate-beam`, `RequireAdminRoute`, ADMIN-only.
  (Worth stating: a declared-but-unrouted admin page has shipped here before.)
- Run list from `GET /runs` — corridor, employee type, candidate count, passes
  completed/requested, failed badge.
- Review panel from `GET /runs/{id}/items` — rank, verbatim title, confidence band,
  "seen in N/M passes", flagged badge, unsourced state, expandable per-pass variants.
- Per-item Approve/Reject with a review note → `POST /items/{id}/review`.
- Import **preview** → `POST /runs/{id}/import-plan`, with each skipped candidate and its reason.
- Counts strip: total / pending / approved / rejected / imported / source_missing.
- Errors rendered inline rather than in a toast.
- 11 tests, all aimed at the honesty invariants (no promote control, source shown as a
  claim, unsourced shown as worklist, never "verified"/"compliant").

## Missing and buildable — this is the delta

- Execute Import button + confirmation modal + success banner + 409 handling.
- Verify Import button + per-item verification results and diffs.
- The spec's verbatim yellow notice (the page carries different wording today).
- "Select Near-Certain" bulk action and an "N of M approved" running count.
- Grouping the review panel by pillar.

## Missing and BLOCKED — no backend exists

> **SUPERSEDED for item 1, same day.** Commit `7d48945e` ("give the beam an entry point")
> landed on this branch *while this audit was being written* and adds the missing writer
> (`imports/candidate_beam/store.py`) plus `POST /runs`, `POST /runs/{id}/pass`,
> `POST /runs/{id}/finalize`. The launch console is no longer blocked — but it is also not
> the shape the spec assumes. See "Launch console, after 7d48945e" below. Item 2 (the
> Source URL field) still stands.

**1. The launch console cannot be built.** *(true when audited; see the note above)*

There is no `POST /runs` endpoint. The router exposes exactly: `GET /runs`,
`GET /runs/{id}/items`, `POST /items/{id}/review`, `POST /runs/{id}/import-plan`,
`GET /pillars`, `POST /runs/{id}/import`, `GET /runs/{id}/import-verify`.

Worse than a missing route: `pipeline.run_beam()` is a **pure function with no production
caller** — the only references are in tests. Nothing anywhere writes `candidate_beam_runs`
or `candidate_beam_items`. The tables are not "empty until someone runs a beam"; there is
no code path that can run one. A launch form would post to a route that does not exist,
and even a created run would have nothing to execute it.

This needs a run-creation endpoint, a persistence writer, and background execution — that
is backend work of the same size as Action 3, not admin-UI gap-fill.

**2. The Source URL field on unsourced candidates cannot be built.**

The spec asks for a required Source URL input that gates approval. `ReviewRequest` accepts
only `{status, review_note}` — no endpoint writes a source onto a candidate. Adding the
field would collect a URL and discard it, which is worse than not offering it: the reviewer
would believe the research was captured.

## Wrong in the spec — reality differs

| Spec says | Reality |
|---|---|
| `POST /runs/` returns a run_id | no such endpoint |
| import body `{approved_ids: [...]}` | `{country, pillar_overrides, dry_run}`; approval is already persisted per item |
| approve = an unchecked checkbox | approve is a server-side status via `POST /items/{id}/review` |
| — | **`dry_run` defaults TRUE** — an Execute button that omits it previews and writes nothing |
| verify: 409 means "already imported" | on **verify**, 409 means drift was found and carries the full report; it must be rendered, not treated as an error |
| run status `running` | vocabulary is `generating \| pending_review \| failed` |
| group by pillar | `BeamItem` has `category`; pillar comes from `/pillars` or `import-plan.pillar_by_uid` |
| "all 35 candidates", `pass_frequency == 5` | both are per-run (`passes_total`); `confidence_band === 'near-certain'` is the stable selector |

## Unrelated defect found during the audit

`supabase/migrations/20261106000000_candidate_beam.sql` collides with
`20261106000000_corridor_deadline_events.sql` on PR #1885. The prod ledger was repaired to
version `20261106000000` naming `corridor_deadline_events`, so the ledger can no longer
distinguish the two — it is keyed by version and tracks only one file per version. Both
tables exist in prod; only one is recorded. One of the two migrations needs restamping
above the ledger max before either PR merges.


## Launch console, after `7d48945e`

The endpoint exists now, so the console is buildable — but the spec's single call does not
match what shipped, and building to the spec literally would hang the browser on five paid
model calls.

The backend is deliberately **resumable, not atomic**:

| Spec assumes | Backend provides |
|---|---|
| `POST /runs/` returns a finished run | `POST /runs` opens a row at status `generating` and returns immediately |
| one call runs the beam | `POST /runs/{id}/pass` runs **exactly one** pass, called N times; omitting `pass_number` runs the lowest incomplete slot, which is also how a failed pass is retried |
| — | `POST /runs/{id}/finalize` clusters and ranks once the passes are in |
| spinner while `status: running` | the status vocabulary is `generating \| pending_review \| failed`; there is no `running` |

So the console has to drive `start → pass × N → finalize` from the client, showing per-pass
progress rather than one opaque spinner. That is a better screen than the spec describes —
a five-pass beam behind a single request is a gateway timeout that loses every completed
pass — but it is a different screen, and the difference is the reason it was left for a
decision rather than guessed at.

`StartRunRequest` also takes `passes` (2–7, default 5) and an optional `model`, neither of
which the spec's form mentions.

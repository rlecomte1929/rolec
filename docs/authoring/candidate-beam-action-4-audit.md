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

**1. The launch console cannot be built.**

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

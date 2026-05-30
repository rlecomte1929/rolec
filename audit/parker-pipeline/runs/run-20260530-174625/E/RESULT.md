# Step E RESULT — RLHF-lite preference dataset from Notion Human Review

_Run: run-20260530-174625 | Branch: audit/parker-step-E-rlhf-lite (stacked on audit/parker-step-D-prompt-registry)_

## Summary
Step E turns human review verdicts into a preference signal on top of D's prompt
registry. A new `POST /api/ai/feedback` route records approved/rejected/edited
verdicts into a new `ai_human_feedback` table, deriving each row's
`prompt_version_id` + `canary_arm` from the referenced trace (attribution is never
trusted from the client). A builder service converts those verdicts into DPO
`{prompt, chosen, rejected}` pairs (edited-text pairs + cross-arm approve/reject on
the same `query_hash`) and computes per-version win rates with a Wilson 95% CI. The
admin prompts page from D gains a single "Win rate" column fed by a new
`GET /api/admin/prompts/{task_key}/win-rates` route. A CLI exports the pair set as
JSONL for offline DPO training. This closes the RLHF-lite loop: ship a prompt version
(D) → collect human verdicts (E) → measure which version wins and emit training data.

## Files changed
This is a **stacked PR on `audit/parker-step-D-prompt-registry`**, so `main...HEAD`
also contains D's (and earlier branches') commits. The diff below is **E-only**
(`git diff audit/parker-step-D-prompt-registry...HEAD --stat`):

```
 .gitignore                                         |   3 +
 backend/app/main.py                                |   2 +
 backend/app/routers/admin_prompts.py               |  21 +-
 backend/app/routers/ai_feedback.py                 |  52 +++++
 backend/app/services/ai_feedback_service.py        | 122 ++++++++++
 backend/app/services/preference_dataset_builder.py | 257 +++++++++++++++++++++
 backend/scripts/export_preference_dataset.py       |  73 ++++++
 backend/tests/test_ai_feedback_router.py           | 144 ++++++++++++
 backend/tests/test_preference_dataset_builder.py   | 228 ++++++++++++++++++
 frontend/src/api/client.ts                         |  15 ++
 frontend/src/pages/admin/AdminPrompts.tsx          |  38 ++-
 .../pages/admin/__tests__/AdminPrompts.test.tsx    |  23 +-
 .../20260601060000_ai_human_feedback.sql           |  78 +++++++
 13 files changed, 1052 insertions(+), 4 deletions(-)
```

## Tests added
- `backend/tests/test_ai_feedback_router.py` — 401 without auth; happy-path POST lands
  with attribution derived from the trace (`prompt_version_id=v-canary`,
  `canary_arm=canary`); idempotent re-submit updates the same row (1 row, verdict
  flips); bad verdict → 422; unknown trace → 404.
- `backend/tests/test_preference_dataset_builder.py` — edited verdict yields a pair
  whose `chosen` is the edited text; cross-arm same-`query_hash` approve/reject yields
  a pair with canary chosen / prod rejected; empty feedback → no pairs; win-rate math
  + CI (8/10 ⇒ 0.8, `ci_low ≤ rate ≤ ci_high` within [0,1]); Wilson zero-total ⇒ all
  zeros; FK to `prompt_versions` is enforced (bogus version id ⇒ IntegrityError);
  JSONL writer is well-formed (`prompt`/`chosen`/`rejected`/`metadata.source`).

## Test result
- pytest (E test files): **12 passed in 0.40s** (`test_preference_dataset_builder.py`
  7, `test_ai_feedback_router.py` 5). The full backend suite has pre-existing
  cross-module collection errors unrelated to E, so E's files were run directly.
- tsc: **pass** (`npx tsc --noEmit` exit 0).
- frontend vitest: `AdminPrompts.test.tsx` **3 passed** (added explicit
  `afterEach(cleanup)` — see Deviations).

## Migration applied?
- File: `supabase/migrations/20260601060000_ai_human_feedback.sql` — **NOT applied**
  (left for human review → MCP `apply_migration`; `supabase db push` is blocked by
  remote history drift).
- RLS posture:
  - Table `ai_human_feedback`: RLS **enabled**. Policies — admin `SELECT` via
    `public.is_admin()`; `service_role` `ALL` (backend writes go through the service
    role / SQLAlchemy). `GRANT SELECT TO authenticated` is intentionally **not**
    granted broad write; `REVOKE ALL ... FROM anon` present. Satisfies the CLAUDE.md
    hard gate (RLS on + ≥1 policy + anon revoked).

## New routes
| Method | Path | Auth gate | Router file |
|--------|------|-----------|-------------|
| POST   | /api/ai/feedback | session-token (`get_current_user`) | backend/app/routers/ai_feedback.py |
| GET    | /api/admin/prompts/{task_key}/win-rates | is_admin (`require_admin`) | backend/app/routers/admin_prompts.py |

## New tables / schema changes
- `ai_human_feedback` — `id uuid pk`, `trace_session_id text not null`,
  `reviewer_user_id text not null`, `verdict text check in (approved,rejected,edited)`,
  `edited_output_json jsonb`, `comment text`,
  `prompt_version_id uuid references prompt_versions(id)`, `canary_arm text`,
  `created_at timestamptz default now()`, `unique (trace_session_id, reviewer_user_id)`.
  Indexes: `idx_ai_human_feedback_version_verdict (prompt_version_id, verdict)`,
  `idx_ai_human_feedback_trace (trace_session_id)`.

## Configuration / env vars added
- None. The export CLI takes `--task-key` / `--out` / `--min-pairs` flags; output
  defaults to `preferences/<task>_<YYYYMMDD>.jsonl` (gitignored).

## UI changes summary
- New routes added: none.
- New components added: none.
- Existing antigravity components reused: the prompts table from D (Card, Button,
  Badge, Alert, Input) — a single "Win rate" column + tooltip were added to the
  existing table; no new primitives.
- UI-PROPOSAL.md status: not required (single column on an existing page, below the
  "significant UI change" threshold).

## Deviations from the original audit prompt
- **Attribution derived server-side from the trace**, not accepted from the client
  payload — the original sketch had the client send `prompt_version_id`. Deriving it
  from `policy_assistant_traces` prevents spoofed attribution.
- **`ai_human_feedback.trace_session_id` is `text`**, matching D's actual
  `policy_assistant_traces.id TEXT PRIMARY KEY` (a legacy bootstrap table), not a uuid
  as the sketch assumed.
- **Builder/SQL kept portable PG+SQLite** (JSON bindparam, `excluded.*` upsert, no
  `RETURNING`) so the service is unit-testable on in-memory SQLite.
- **Frontend test cleanup**: vitest has no `globals: true` / setup file, so
  `@testing-library/react` auto-cleanup never fired and prior-test DOM leaked
  ("Found multiple elements"). Added explicit `afterEach(cleanup)` to the test file —
  root-cause fix, not a skip.

## What downstream steps will need from this step
- Human verdicts are written via `POST /api/ai/feedback` with body
  `{trace_session_id, verdict, edited_output_json?, comment?}` where `verdict ∈
  {approved, rejected, edited}`. The row's `prompt_version_id` + `canary_arm` are
  derived from the referenced trace — do not send them.
- Preference pairs: `preference_dataset_builder.build_dpo_pairs(task_key,
  min_pairs=50, session=None)` → `list[DPOPair(prompt, chosen, rejected, task_key,
  chosen_version_id, rejected_version_id, source)]`; `source ∈ {edited, cross_arm}`.
- Win rates: `compute_win_rates(task_key, session=None)` →
  `dict[version_id -> WinRate(version_id, approvals, total, win_rate, ci_low, ci_high)]`
  (Wilson 95% CI; edited + rejected both count as non-wins). Also exposed at
  `GET /api/admin/prompts/{task_key}/win-rates`.
- Export: `python -m backend.scripts.export_preference_dataset --task-key <k>` writes
  JSONL `{prompt, chosen, rejected, metadata}` lines under `preferences/`.

## Known gaps / follow-ups
- Migration not applied — needs human MCP `apply_migration` (history-drift constraint).
- No write path yet from the Notion Human Review queue into `POST /api/ai/feedback`;
  E provides the sink + math but the Notion→API sync is a follow-up.
- Cross-arm pairing keys on exact `query_hash` equality; near-duplicate queries across
  arms won't pair. Acceptable for v1; revisit if pair yield is low.

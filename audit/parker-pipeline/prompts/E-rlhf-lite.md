## Task body — step E

**UI impact:** Adds a single win-rate column to D's existing `/admin/prompts`
page. No new pages, no new components. Reuses the table primitive from D.

Close the loop between Notion's Human Review queue and model quality by emitting a
preference dataset suitable for DPO-style fine-tuning or for re-ranking prompt-registry
canaries. This is the cheap version of RLHF: log human verdicts, build pairs, surface
win rates.

### Prerequisites from prior steps — REQUIRED READING

**You depend on step D.** Before writing any code, read:
- `audit/parker-pipeline/runs/<RUN_ID>/D/RESULT.md`

Pay attention to:
- The exact `prompt_versions` schema D shipped (column names, types).
- The canonical task_key set D documented.
- The `ActivePrompt` dataclass shape — your feedback must reference `prompt_version_id`.
- The TraceSession columns D extended (`prompt_version_id`, `canary_arm`).

Your code MUST use D's actual schema, not what the original audit doc sketched.

If D's RESULT.md is missing or D's status in STATE.json is not `completed`, **stop and
write BLOCKED.md**.

### Source material
- `backend/app/services/ai_trace_logger.py` — TraceSession model.
- The `notion-review-validator` skill at
  `/var/folders/.../anthropic-skills/notion-review-validator/SKILL.md` — defines the
  review payload shape (approved/rejected/edited).
- `audit/parker-framework-audit.md` section 2 (W10) and section 4, Prompt E.

### Concrete deliverables

1. Migration `supabase/migrations/<timestamp>_ai_human_feedback.sql`:
   - Table `ai_human_feedback(
       id uuid pk,
       trace_session_id uuid not null fk → policy_assistant_traces.id,
       reviewer_user_id uuid not null,
       verdict text not null,                  -- approved|rejected|edited
       edited_output_json jsonb,
       comment text,
       prompt_version_id uuid fk → prompt_versions.id,  -- from D
       canary_arm text,                        -- 'prod' or 'canary', for attribution
       created_at timestamptz not null default now()
     )`.
   - Unique on `(trace_session_id, reviewer_user_id)` — idempotency.
   - Index on `(prompt_version_id, verdict)` for win-rate aggregation.
   - **RLS enabled**. SELECT for admins; INSERT for the service role only.
     `REVOKE ALL ... FROM anon`.
2. Backend route in `backend/app/routers/ai_feedback.py`:
   - `POST /api/ai/feedback` — body `{trace_session_id, verdict, edited_output_json?,
     comment?}`. Idempotent on `(trace_session_id, reviewer_user_id)`. Derives
     `prompt_version_id` and `canary_arm` by joining to the trace.
   - Auth: session-token (any authenticated user who is a reviewer).
   - Register in `backend/app/main.py`.
3. Create `backend/app/services/preference_dataset_builder.py`:
   - `build_dpo_pairs(task_key: str, min_pairs: int = 50) -> list[DPOPair]` —
     returns chosen/rejected pairs in the canonical `{prompt, chosen, rejected}`
     JSONL shape. Pairs are formed by matching trace_sessions on the same
     `(prompt_template_hash, input_hash)` where the canary arm was approved and
     the prod arm was rejected (or vice-versa).
   - `compute_win_rates(task_key) -> dict[version_id, WinRate]` — per-version
     win rate (approvals / total verdicts) plus 95% CI.
4. CLI: `python -m backend.scripts.export_preference_dataset \
     --task-key policy_classification \
     --out preferences/policy_classification_$(date +%Y%m%d).jsonl`.
   Writes a newline-delimited JSON file. Creates the `preferences/` directory if
   missing. Adds `preferences/` to `.gitignore` (do not commit datasets).
5. Surface win rates in the admin prompts page from D:
   - Extend `frontend/src/features/admin/prompts/PromptsPage.tsx` (modifying D's
     file) to show per-version win rate next to the version.
   - Use the new endpoint `GET /api/admin/prompts/{task_key}/win-rates`.
6. Tests:
   - `backend/tests/test_ai_feedback_router.py` — idempotency, auth, schema.
   - `backend/tests/test_preference_dataset_builder.py` — pair construction
     correctness; empty trace → empty pairs without error.
   - Snapshot test for the JSONL writer.

### Design notes
- **Do not auto-fine-tune anything** in this step. The deliverable is the dataset
  and the loop, not the training run.
- A Notion review may produce verdicts in three shapes (approved, rejected,
  edited). Treat `edited` as "rejected for the original output, approved for the
  edited output" — both rows go into the feedback table with appropriate verdict.
- Pair construction: only pair where the two trace_sessions answered the same
  underlying question (same input hash) AND received different arms. That is the
  only honest A/B signal you can extract from organic traffic.
- Win-rate CI: use Wilson interval — Romain will read these numbers in product
  meetings, naive ±√(p(1-p)/n) is misleading for small n.

### Out of scope
- DPO training itself.
- A self-serve labelling UI inside ReloPass. Notion is the review surface.

### Acceptance criteria
- pytest + tsc both pass.
- Migration applies; FK to `prompt_versions` is enforced (test it).
- The Notion skill can POST to /api/ai/feedback and the row lands with the right
  `prompt_version_id` and `canary_arm` (test with a mocked trace).
- CLI produces a well-formed JSONL with ≥1 pair on a fixture seed.
- Admin page shows win rates per version.

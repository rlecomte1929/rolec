## Task body — step D

**UI impact:** ONE small admin table page at `/admin/prompts`. Reuses
`frontend/src/components/antigravity/` primitives (Card, Table, Button, Badge)
and follows the closest existing admin page as its visual model (e.g. the
suppliers admin page — find it via `ls frontend/src/features/admin/`). Does NOT
require UI-PROPOSAL.md because it's a single utilitarian admin table inside an
existing admin area, no new chart types, no new modal patterns.

Build a prompt registry so system prompts and few-shot examples are versioned,
A/B-testable, and rollback-able. Today prompts live as string literals in Python
modules — invisible to product, untraceable in `git log`, impossible to A/B-test.
This step is a **platform unlock**: steps E, F, and I all depend on it.

### Prerequisites from prior steps
_None — D is independent. But three downstream steps (E, F, I) depend on D, so the
schema and API you ship here are contractual. Be deliberate._

### Source material
- `backend/relopass/llm/router.py` — the existing deterministic LLM router.
- `backend/app/services/ai_trace_logger.py` — TraceSession schema you will extend.
- `backend/app/services/llm_policy_extractor.py` and
  `backend/app/services/policy_assistant_rag_engine.py` — current consumers with
  hardcoded prompts.
- `audit/parker-framework-audit.md` section 2 (W12) and section 4, Prompt D.

### Concrete deliverables

1. Migration `supabase/migrations/<timestamp>_prompt_registry.sql`:
   - Table `prompt_versions(
       id uuid pk,
       task_key text not null,                   -- e.g. 'policy_classification'
       version int not null,                     -- monotonically increasing per task_key
       system_prompt text not null,
       user_template text,                       -- jinja2-like {{var}} placeholders
       model_name text not null,                 -- e.g. 'claude-sonnet-4-6'
       temperature numeric not null default 0.0,
       max_tokens int not null default 1024,
       status text not null default 'draft',     -- draft|canary|prod|archived
       created_at timestamptz not null default now(),
       created_by uuid,
       notes text
     )`.
   - Unique on `(task_key, version)`.
   - Partial unique index: at most one `status='prod'` per `task_key`.
   - Table `prompt_routing(
       task_key text pk,
       canary_share numeric not null default 0.0  -- 0.0–1.0
     )`.
   - **RLS enabled** on both. SELECT for authenticated; INSERT/UPDATE for admins
     only. `REVOKE ALL ... FROM anon` on both.
2. Create `backend/app/services/prompt_registry.py`:
   - `get_active_prompt(task_key: str) -> ActivePrompt` — returns a typed dataclass
     `ActivePrompt(id, version, system_prompt, user_template, model_name,
     temperature, max_tokens, canary_arm)`. Performs the canary split using
     `random.random() < canary_share`; the chosen `canary_arm` is `'prod'` or
     `'canary'` and is logged for downstream attribution.
   - `render_user_message(template, variables) -> str` — simple `{{name}}`
     substitution (no jinja runtime — keep it dependency-free).
   - `list_versions(task_key)`, `promote(version_id, target_status)`,
     `set_canary_share(task_key, share)`.
3. **Refactor** the two existing consumers to use the registry:
   - `backend/app/services/llm_policy_extractor.py` — replace string literals with
     `prompt_registry.get_active_prompt('policy_extraction')`.
   - `backend/app/services/policy_assistant_rag_engine.py` — likewise for
     `policy_assistant_answer`.
   - Seed the registry with the current prompts as `version=1, status='prod'` in
     the migration (or a follow-up data migration).
4. Extend `TraceSession` in `ai_trace_logger.py` to record
   `prompt_version_id` and `canary_arm`. Confirm the policy_assistant_traces table
   supports these columns (add a migration step if not).
5. Admin routes in a new `backend/app/routers/admin_prompts.py`:
   - `GET /api/admin/prompts` — list task_keys and the active prod + canary version.
   - `GET /api/admin/prompts/{task_key}` — list all versions.
   - `POST /api/admin/prompts` — create a new draft version.
   - `POST /api/admin/prompts/{version_id}/promote` — body `{status: 'canary'|'prod'}`.
   - `POST /api/admin/prompts/{task_key}/canary-share` — body `{share: 0..1}`.
   - Auth: `is_admin()` allowlist for all routes.
   - Register in `backend/app/main.py`.
6. Minimal frontend at `frontend/src/features/admin/prompts/PromptsPage.tsx`:
   - Table listing task_key, prod version, canary version, canary share.
   - Per task: list of versions with promote / archive buttons.
   - Route: `/admin/prompts`, gated by admin role guard.
   - Use the `frontend/src/components/antigravity/` design system per CLAUDE.md.
7. Tests:
   - `backend/tests/test_prompt_registry.py` — canary split is ~10% over 10k draws
     (chi-square within tolerance); promote demotes prior prod; partial unique
     index prevents two prod rows.
   - `backend/tests/test_admin_prompts_router.py` — auth gates, 200 happy path.
   - `frontend/src/features/admin/prompts/__tests__/PromptsPage.test.tsx` —
     renders table, promote button calls the right endpoint (mocked).

### Design notes
- This is the **contract** for downstream steps. Document the schema and the
  `ActivePrompt` shape exactly in RESULT.md. Downstream steps will read RESULT.md
  to know the canonical task_key values.
- Canary attribution: every TraceSession row must record which arm served the
  response so eval pipelines can compute per-arm win rates.
- Keep dependency-free: no jinja2. The `{{var}}` substitution is intentionally
  trivial.
- Do not break the existing two consumers. The seeded `version=1, status='prod'`
  must reproduce today's prompts byte-for-byte.

### Out of scope
- The actual A/B win-rate dashboard (next sprint).
- Few-shot example management beyond a single `notes` field.

### Acceptance criteria
- pytest + tsc both pass.
- Migration applies; partial unique index prevents two prod rows for the same
  task_key (test it).
- The two refactored consumers produce identical outputs against a fixture set
  before and after the refactor (snapshot test).
- The admin page renders and the promote button works against a mocked API.
- RESULT.md documents the canonical task_key set and the `ActivePrompt` shape —
  downstream steps E, F, I will rely on this.

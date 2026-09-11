# Review request — form-onboarding pipeline spec (code-grounded, for Cursor)

**For:** a repo-attached agent (Cursor) that can read the ReloPass codebase.
**Subject spec:** [`docs/superpowers/specs/2026-09-11-form-onboarding-pipeline-design.md`](2026-09-11-form-onboarding-pipeline-design.md)
(v2, on branch `claude/form-onboarding-spec`).

## Why this review is different (read first)

This spec has already had one thorough **repo-blind** external review (spec text + web standards, no
codebase access). That review's blockers are already folded into v2 (§ below). **Your job is the
complementary half: validate the spec against the _actual code_.** Do not re-derive the standards review;
find where the spec's assumptions about *this repo* are wrong, where it will collide with real code,
what it should reuse instead of building, and whether the scope is realistic for this codebase's current
state. Ground every finding in specific files/lines.

## What the spec proposes (one paragraph)

A demand-driven, fully-automatic pipeline that onboards a new government AcroForm: acquire the official
PDF → analyze/classify fields → LLM-propose field→`fact_key` mappings (authoring layer) → deterministic
guards + a 4-gate verification (structural, sentinel round-trip, semantic, rendering) → publish an
**immutable form version** and switch an active-version pointer atomically → the employee form-view page
offers it. A DB queue with `SKIP LOCKED` leases is the durable substrate; a GitHub Actions job is the
executor. Per-form config becomes typed **data** (`form_field_mappings` gains `field_kind` +
`transform_spec`, version-scoped), so `CHOICE_GROUPS` and the date-part rules move out of code.

## Code-grounded questions (the value-add — please answer each with file:line evidence)

1. **`form_field_mappings` version-scoping & its consumers.** The spec re-keys mappings to a
   `form_version_id` and adds `field_kind` + `transform_spec`. Find every consumer of
   `form_field_mappings` (start: `backend/app/services/form_prefill_service.py` — `_load_field_mappings`,
   `get_available_forms`, `visa_types_for_corridor`; the seed migrations; any router). What breaks under
   version-scoping? Is there a migration path that keeps the current FR/ES forms working throughout?

2. **Migration feasibility.** The spec adds ~7 tables + column changes. Given the repo's migration
   reality (the Supabase↔GitHub applier is jammed at `MIGRATIONS_FAILED`, ledger drift, the PG16-parity
   lane, `db push` forbidden — see `CLAUDE.md` "Migration discipline"), is a 7-table addition realistic,
   and how? What's the smallest schema slice that unblocks Phase 1 without a large risky migration set?

3. **Serve/LLM isolation guard efficacy.** The spec's #1 hard gate relies on
   `scripts/check_serving_llm_isolation.py` to keep the LLM mapper off the serve path. Verify against the
   guard's actual code: (a) Is `form_prefill_service` (the *fill* path) inside or outside the
   `SERVING_ROOTS` closure? (b) Would the guard **actually fail** if the new mapper module were
   import-reachable from a serving root — including lazy/function-local imports? (c) The spec also wants
   the mapper unreachable from the *fill* path — does the guard cover that, or is a new assertion needed?

4. **`CHOICE_GROUPS` → data refactor safety.** The spec moves radio config + date-part rules from code
   into `form_field_mappings` rows read at fill time. Find *all* consumers of `CHOICE_GROUPS`,
   `build_choice_fill`, `RadioField`, `_resolve_checkbox_states`, and the `date_day/month/year` rules.
   Will the refactor preserve behaviour so the **36 form-fill tests** (`test_imm11_form_prefill`,
   `test_form_choice_fill`, `test_fr_cerfa_real_*`, `test_es_ex17_real_pdf_fill`) pass unchanged? Any
   hidden coupling (e.g. `generate_prefilled_pdf` flow, `reconcile_report_against_pdf`)?

5. **Atomic publish across two stores.** The spec requires publishing an immutable artifact + switching
   `active_version_id` "transactionally," and never overwriting the live version. Postgres and Supabase
   **Storage are separate systems** — there is no cross-store transaction. Given how the repo talks to
   Storage today (`form_prefill_service._upload_output` / `supabase_client`), is the atomic-publish design
   achievable, and what's the concrete safe sequence (write immutable object → verify → DB pointer swap)?

6. **Durable queue on the Supabase pooler.** The spec uses `FOR UPDATE SKIP LOCKED` for lease-based
   claiming. The prod `DATABASE_URL` is the Supabase **transaction-mode pooler (port 6543)**, which breaks
   session-level features (see the `prepared statement` gotcha in `CLAUDE.md`). Does `SKIP LOCKED`/row
   locking work correctly through that pooler for a worker, or does the worker need a session-mode
   (5432) connection? Implications for the design.

7. **Executor + secrets reuse.** Is there an existing GitHub Actions pattern to reuse for the worker
   (e.g. `immigration-indexer` / the RAG indexer workflow), including how it holds the Supabase service
   key + how secrets are scoped? Is a "least-privilege worker DB role" achievable on this Supabase
   project, or is the broad service key the only realistic option (and what's the isolation story)?

8. **Reuse vs. greenfield.** Point to existing building blocks the pipeline should reuse rather than
   rebuild: RLS policy templates for an admin/system table; the authoring-layer location (`backend/app/`
   layout, `AGENTS`/`agents` vs a new `authoring/` package — where does authoring-time code belong today?);
   the fill primitives (`fill_acroform`, `build_fill_plan`, `_resolve_checkbox_states`,
   `reconcile_report_against_pdf`); the worklist (`docs/form-autofill/form-acquisition-worklist.md`) as the
   authority/source catalog; the fact registry (`backend/app/services/fact_dictionary.py`) as the mapping
   target vocabulary — does it carry the semantics/versioning the spec assumes, or would it need a version/hash?

9. **Spec claims about the code that may be wrong.** Flag anything the spec asserts about the codebase
   that isn't true: e.g. "`form_prefill_service` is not a serving root"; "the 36 tests"; the dual
   router-registration requirement (`backend/main.py` + `backend/app/main.py`); "register ALTERs in the
   PG16-parity lane"; whether an "authoring layer" directory even exists yet.

10. **Effort & sequencing realism.** Given the codebase's actual state (backend monolith + `app/` modular
    layer, free Render tier that spins down, jammed migration applier, single primary maintainer), is the
    v2 scope realistic? Which phase (§15 roadmap) is the right *first* PR, and what would you cut or defer?

## The standards review's four blockers (already in v2 — validate them against the code, don't re-derive)

1. **Semantic verification gap** — `0 not_in_pdf` proves a box exists/accepts a value, not that the value
   answers the right question. v2 adds a semantic-evidence gate + sentinel round-trip + precision-over-recall.
   *Code question:* is the sentinel round-trip actually implementable with the current `fill_acroform` +
   `reconcile_report_against_pdf`?
2. **Form-edition/versioning** — logical form ≠ immutable version; atomic active-version publish.
   *Code question:* see Q1/Q5.
3. **SSRF-hardened acquisition** — origin allowlist, IP/redirect validation, resource limits, isolated parse.
   *Code question:* Render is "native, no apt" (`CLAUDE.md`) and the worker is GH Actions — where does the
   constrained fetch/parse actually run, and are the limits enforceable there?
4. **Transactional durable queue/publish** — DB leases (`SKIP LOCKED`), atomic non-destructive publish.
   *Code question:* see Q5/Q6.

## Deliverable

Write your review to `docs/superpowers/specs/2026-09-11-form-onboarding-cursor-review.md` on a branch and
open a **draft PR** (do not merge). Structure: a short verdict (approve-with-changes / revise / other),
then per-question findings with `file:line` evidence, then a prioritized list of *code-grounded* changes
the spec needs, then your recommended first-PR slice. Where you agree the spec already handles something,
say so briefly — the goal is the delta the codebase reveals, not a restatement of the spec.

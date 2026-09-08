# ATT-2/ATT-3 build lane — Claude Code prompt (the 3 independent starters)

**Paste into a Claude Code session in `rolec`.** Runs the three subtasks that have no unmet dependencies — two additive migrations + one behaviour-preserving refactor — on one branch. All 🟡, additive, zero serving impact. This unblocks ATT-2.2 (2104) and ATT-3.2 (2109) next.

---

```
TASK — Execute the three unblocked Counsel-Attestation foundation subtasks on ONE branch.
These are independent, additive, and change NO serving behaviour. Follow relopass-dev-queue
discipline: recon → implement following existing patterns → TypeScript/pytest validation →
per-task commit → update the Notion card. Branch only; open ONE PR at the end; do NOT merge.

Notion cards (each has a full Execution Prompt in its body — read it):
- AIQ-2103  [ATT-2.1]  Migration: add promotion_policy + advance_review_status to corridor_attestation_requests
- AIQ-2105  [ATT-2.3]  Refactor promote() → shared _apply_promotion(db, req, *, actor, advance_review_status=False)
- AIQ-2108  [ATT-3.1]  Migration: add case_id scope to corridor_attestation_requests

Branch: feat/att-foundations

AIQ-2103 (migration):
- Follow the newest file in supabase/migrations/ for style.
- Up: ALTER TABLE public.corridor_attestation_requests
    ADD COLUMN promotion_policy text NOT NULL DEFAULT 'manual',
    ADD CONSTRAINT ck_cap_promotion_policy CHECK (promotion_policy IN ('manual','auto_on_sign')),
    ADD COLUMN advance_review_status boolean NOT NULL DEFAULT false;
  Down: drop both (and the constraint).
- Validate on a disposable/staging PG (never prod): apply + rollback; existing rows read 'manual' / false.
- Nothing reads these columns yet — this is purely additive.

AIQ-2108 (migration):
- Up: ALTER TABLE public.corridor_attestation_requests ADD COLUMN case_id uuid NULL;
    CREATE INDEX ix_cap_case_id ON public.corridor_attestation_requests (case_id);
  (The scope text column already exists — 'case' becomes a valid value by convention; no enum change.)
  Down: drop index + column.
- Validate: apply + rollback; existing corridor requests unaffected (scope='legal', case_id NULL).

AIQ-2105 (refactor — behaviour-preserving, NO functional change):
- File: backend/app/routers/attestation.py, promote_attestation (~L359-434).
- Extract the body into _apply_promotion(db, req, *, actor: str, advance_review_status: bool = False)
  -> AttestationPromoteResultDTO: the status=='signed' check, the signed_content_hash == content_snapshot_hash
  check, approved-only selection, per-item attestation_status='attested' + attested_by/attested_at/
  latest_attestation_request_id, and the len(promoted)!=len(approved) partial-write guard.
  The admin promote endpoint calls it with advance_review_status=False (identical behaviour).
- advance_review_status is accepted but UNUSED in this subtask (wired in ATT-2.4). Leave a
  # TODO [ATT-2.4] where the review_status advance will go.
- Validate: the existing attestation tests (pytest backend/tests -k attestation, 43 tests) all pass
  UNCHANGED — this refactor must be invisible to behaviour.

Order within the session: do the two migrations first (independent), then the refactor. Run the full
attestation test suite after the refactor and confirm 43 still pass. Keep check_serving_llm_isolation
and check_route_auth green.

Per subtask, on success: git commit (one commit each, message referencing the AIQ id), and update the
Notion card → Status 'Human Review', Final Validation Result 'Passed', Execution Notes with the commit SHA
+ what was validated. Then flip the now-unblocked cards: AIQ-2104 [ATT-2.2] and AIQ-2109 [ATT-3.2] from
'Blocked' → 'Ready for AI' (their only dependency was these).

At the end: open ONE PR (feat/att-foundations) with all three commits; do NOT merge — hand Romain the diff.
Report: the three results, the test counts, the PR link, and confirm 2104 + 2109 are now Ready for AI.

GOVERNANCE: disposable/staging DB for migration validation — never apply to prod from here; the real
migration is applied via the normal deploy path after PR review. Branch + PR only; no direct main merge.
```

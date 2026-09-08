# ATT-2.2 + ATT-3.2 build prompt — Claude Code (the next unblocked pair)

**Paste into a Claude Code session in `rolec`.** Builds the two subtasks whose only dependency (the #1995 migrations) is now satisfied on the `feat/att-foundations` branch. Both are 🟡, both read the new columns — so they build/test against a DB that HAS the migration applied, and they must not deploy to prod until the migration is applied to prod.

---

```
TASK — Execute the two now-unblocked Counsel-Attestation subtasks. Follow relopass-dev-queue
discipline: recon (never skipped) → implement following existing patterns → pytest validation →
per-task commit → update the Notion card. Branch + ONE PR; do NOT merge.

Cards (each has a full Execution Prompt in its body — read it first):
- AIQ-2104  [ATT-2.2]  Accept promotion_policy on create + optionally include pending rows
- AIQ-2109  [ATT-3.2]  Case snapshot builder — snapshot a case's served requirements (PII-preserving)

BRANCH SETUP — these depend on #1995's columns:
- #1995 (feat/att-foundations) adds promotion_policy, advance_review_status, case_id. It is NOT
  merged. Branch this work from the tip that HAS those columns: `git checkout feat/att-foundations`
  then `git checkout -b feat/att-create-scopes` (or branch from main if #1995 has since merged).
- Apply the #1995 migration to your LOCAL/STAGING DB before running any test that reads the new
  columns. Confirm with: information_schema shows promotion_policy / advance_review_status / case_id
  on corridor_attestation_requests. (Verified 2026-08-22: prod does NOT have them yet.)
- 🔴 DEPLOY-ORDER RULE: nothing here may deploy to prod until the migration is applied to prod.
  Deploying a read of these columns ahead of the apply 500s prod. This PR stays unmerged/undeployed
  until #1995 is merged AND its migration is applied to prod.

────────────────────────────────────────
AIQ-2104 [ATT-2.2] — create accepts the policy fields
File: backend/app/routers/attestation.py (create_attestation, ~L234-311); backend/app/schemas.py
(AttestationCreateIn).
- Add promotion_policy: str = 'manual' and advance_review_status: bool = False to AttestationCreateIn;
  persist both onto the CorridorAttestationRequest at creation.
- Candidate query today filters review_status == 'approved' (~L242-246) and excludes OPERATIONAL_PILLARS.
  When advance_review_status is True, widen to review_status IN ('approved','pending') (still exclude
  operational pillars unless explicit requirement_item_ids are given).
- INVARIANT: with defaults (promotion_policy='manual', advance_review_status=False) the behaviour and
  the persisted row must be byte-identical to today. The new behaviour is strictly opt-in.
- Do NOT wire auto-promote or review_status advance here — that is ATT-2.4 (AIQ-2106). Leave the
  existing TODO [ATT-2.4] intact.
- Tests: default create unchanged; auto_on_sign + advance includes pending rows in the snapshot and
  the content_hash reflects them; promotion_policy persisted; invalid promotion_policy rejected by the
  DB CHECK. Run: pytest backend/tests -k attestation (43 baseline must still pass).
- Commit referencing AIQ-2104.

────────────────────────────────────────
AIQ-2109 [ATT-3.2] — case snapshot builder (PII-preserving)
File: backend/app/routers/attestation.py (mirror create_attestation; _first_citation_url);
backend/app/services/attestation_tokens.py (content_hash + canonical_payload).
- Add a case-scoped create path/param: given case_id, resolve the case's canonical id boundary via
  the app's resolve_case_ids (per ATT-3.1's note, case_id has no FK and three case tables exist — use
  the resolver, do not hardcode a table), then snapshot the requirement_items the case is ACTUALLY
  served. Reuse the existing serving selection (requirements_builder / requirements_sufficiency /
  applies_to_matcher) rather than re-deriving which rows apply — recon these first.
- Snapshot items in the SAME shape the corridor path uses {requirement_item_id, title, claim,
  source_url, evidence}; persist scope='case' and case_id on the request; content_hash via the same
  attestation_tokens.content_hash (canonical, sorted).
- 🔒 PII BOUNDARY (load-bearing): canonical_payload / AttestationPublicViewDTO is a legal-fields
  WHITELIST. Case data carries employee/company PII — NONE of it may enter corridor_attestation_items,
  the snapshot, or the public envelope. Keep the whitelist; add nothing case-identifying.
- Do NOT wire auto-release here — that is ATT-3.3 (AIQ-2110).
- Tests: a case request snapshots the correct served rows; content_hash is stable across re-fetch;
  a PII assertion proves the public envelope contains zero case/employee/company PII. 
- Commit referencing AIQ-2109.

────────────────────────────────────────
CLOSE-OUT
- Open ONE PR (feat/att-create-scopes) with both commits; do NOT merge — hand Romain the diff.
- Update Notion: AIQ-2104 and AIQ-2109 → Status 'Human Review', Final Validation Result 'Passed',
  Execution Notes with the commit SHA + what was validated + the deploy-order reminder.
- Flip the now-unblocked cards: AIQ-2106 [ATT-2.4] (needs 2104 + 2105 — both now done) and
  AIQ-2111 [ATT-3.4] (needs 2109) from 'Blocked' → 'Ready for AI'. Leave AIQ-2110 [ATT-3.3] Blocked
  (it needs 2109 AND 2106). Add to each flipped card that its migration dependency is satisfied on a
  branch, not prod — same apply-before-deploy caveat.
- Keep check_serving_llm_isolation and check_route_auth green.
- REPORT: the two results, test counts, the PR link, prod-column status (still absent — expected),
  and confirm 2106 + 2111 are now Ready for AI.

GOVERNANCE: local/staging DB for tests; never apply to prod from here. Branch + PR only; no direct
main merge; nothing deploys ahead of the prod migration apply.
```

# AIQ-2104 [ATT-2.2] — Claude Code prompt (single step)

**Agent: Claude Code** (repo + DB + tests + gh). Not Otto — Otto has no repo/DB access; it's the corridor-research agent only.

Paste into a Claude Code session in `rolec`.

---

```
TASK — Execute AIQ-2104 [ATT-2.2]: make create_attestation accept promotion_policy +
advance_review_status. First step of the ATT-2 chain after the #1995 foundations. Follow
relopass-dev-queue discipline: recon (never skip) → implement to existing patterns → pytest →
commit → update the Notion card. Branch + PR; do NOT merge; nothing deploys to prod.

DEPENDENCY / STATE (verified 2026-08-22):
- Columns promotion_policy, advance_review_status, case_id were added by PR #1995 on branch
  feat/att-foundations. #1995 is NOT merged and the migration is NOT applied to prod — prod
  corridor_attestation_requests currently has none of these columns.
- Branch this work FROM feat/att-foundations so the columns exist:
    git checkout feat/att-foundations && git checkout -b feat/att-2.2-create-policy
  (if #1995 has since merged, branch from main instead).
- Apply the #1995 migration to your LOCAL/STAGING DB before running tests that read the new
  columns. NEVER apply to prod from here.
- DEPLOY-ORDER RULE (load-bearing): this code reads the new columns; it must not deploy to prod
  until the migration is applied to prod. Keep the PR unmerged/undeployed until #1995 is merged
  AND its migration applied. Deploying a read ahead of the apply has 500'd prod before.

RECON FIRST:
- backend/app/routers/attestation.py — create_attestation (~L234-311) and OPERATIONAL_PILLARS (~L79).
- backend/app/schemas.py — AttestationCreateIn.
- The _apply_promotion refactor from AIQ-2105 (commit 26255e25), so you build against the current
  shape, not the old inline promote body.

IMPLEMENT:
- AttestationCreateIn: add promotion_policy: str = "manual" and advance_review_status: bool = False.
- create_attestation: persist both onto the new CorridorAttestationRequest.
- Candidate selection today filters review_status == "approved" and excludes OPERATIONAL_PILLARS.
  When advance_review_status is True, widen to review_status IN ("approved","pending") — still
  excluding operational pillars unless explicit requirement_item_ids are passed.
- Do NOT implement auto-promote or the review_status advance here — that is AIQ-2106 (ATT-2.4).
  Leave the TODO [ATT-2.4] intact.

HARD INVARIANT: with defaults (promotion_policy="manual", advance_review_status=False) the created
row and the API response must be byte-identical to today. The new behaviour is strictly opt-in.

TESTS (pytest backend/tests -k attestation — 43 baseline stays green, plus new):
- default create unchanged (row + snapshot identical to pre-change);
- promotion_policy persisted; an invalid value (e.g. "publish_everything") rejected by the DB CHECK;
- advance_review_status=True includes review_status="pending" rows in the snapshot and the
  content_hash reflects them;
- OPERATIONAL_PILLARS still excluded unless explicit ids.
Keep check_serving_llm_isolation and check_route_auth green.

CLOSE-OUT:
- git commit referencing AIQ-2104; open/refresh a PR (do NOT merge).
- Notion AIQ-2104 → Status "Human Review", Final Validation Result "Passed", Execution Notes with
  the commit SHA, what was validated, and the deploy-order reminder.
- Flip AIQ-2106 [ATT-2.4] from "Blocked" → "Ready for AI" (its deps 2104 + 2105 are now both done),
  adding the same branch-not-prod caveat. Leave 2109/2110/2111/2112 as they are.
- Report: result, test counts, PR link, and confirm prod columns still absent (expected).

GOVERNANCE: local/staging DB for tests; never touch prod; branch + PR only; no direct main merge;
nothing deploys ahead of the prod migration apply.
```

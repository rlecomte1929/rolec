# AIQ-2106 [ATT-2.4] — Claude Code prompt (🔴 auto_on_sign core, single step)

**Agent: Claude Code.** 🔴 changes what can auto-serve — human review before merge. Paste into a Claude Code session in `rolec`.

---

```
TASK — Execute AIQ-2106 [ATT-2.4]: wire auto_on_sign — a valid signature triggers promotion
server-side. 🔴 This CHANGES what can auto-serve: branch + PR, human review before merge, nothing
deploys to prod ahead of the migration apply. relopass-dev-queue discipline.

DEPENDENCY / STATE (verified 2026-08-22):
- Needs the columns (#1995), create_attestation accepting the policy fields (#1997 / AIQ-2104), and
  _apply_promotion (#1995 / AIQ-2105). Branch FROM #1997:
    git checkout feat/att-2.2-create-policy && git checkout -b feat/att-2.4-auto-on-sign
  (or from main if #1995 + #1997 have merged).
- Apply the #1995 migration to LOCAL/STAGING for tests. Prod columns still absent — do not deploy
  ahead of the prod apply.

RECON FIRST:
- attestation.py public_sign (~L537-608) and _apply_promotion (extracted in AIQ-2105).
- The existing gates: public_sign (undecided-items 422; content_hash mismatch 409) and the promote
  gates inside _apply_promotion (signed status, hash match, approved-only, no-partial-write).

IMPLEMENT:
- In public_sign, after the signature row is inserted and status='signed': if
  req.promotion_policy=='auto_on_sign' AND the signer is credentialed (signer_credential non-empty),
  call _apply_promotion(db, req, actor=f'auto:{signer_name}', advance_review_status=req.advance_review_status)
  in the SAME commit.
- When advance_review_status is True, _apply_promotion also sets requirement_items.review_status='approved'
  for the approved items (consummates the pending-inclusion from ATT-2.2). attested_by stays the FIRM,
  not actor (the ATT-2.3 design note).
- Manual policy path unchanged (admin promote still required). Do NOT reimplement the gates — reuse
  _apply_promotion so hash-match + approved-only + no-partial-write stay in one place.
- DB-error hygiene (ATT-2.2 lesson): no raw psycopg2 error may propagate unhandled.

TESTS — per the card note, do NOT delete test_signing_alone_does_not_touch_requirement_items; narrow it
to the manual path and add the auto_on_sign case beside it. Cover:
- auto_on_sign + valid credentialed signature → approved items attested (+ review_status advanced when set);
- manual → signing still touches nothing (admin promote required);
- hash mismatch → no promote; uncredentialed signer → signature recorded, NOT auto-promoted; no-partial-write holds.
pytest backend/tests -k attestation stays green (56+); check_serving_llm_isolation + check_route_auth green.

CLOSE-OUT:
- git commit referencing AIQ-2106; PR (do NOT merge — 🔴).
- Notion AIQ-2106 → Human Review / Passed, notes with SHA + which gates were reused + deploy-order.
- Flip AIQ-2107 [ATT-2.5] and AIQ-2110 [ATT-3.3] Blocked → Ready for AI (2107 needs 2106 ✓; 2110 needs
  2109 ✓ + 2106 ✓), with the branch-not-prod caveat. Leave 2112 Blocked (needs 2110 + 2111).
- Report: result, test counts, PR link, prod columns still absent.

GOVERNANCE: 🔴 changes serving behaviour — human review before any merge; local/staging for tests;
never touch prod; branch + PR only; nothing deploys ahead of the prod migration apply.
```

**Parallel option:** AIQ-2111 [ATT-3.4] (admin "Request validation" button) is also Ready for AI and 🟡 — independent of this one.

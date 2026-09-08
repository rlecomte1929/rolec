# ATT-1 — Claude Code execution prompt (ES→IE counsel-attestation activation dry-run)

**Paste the block below into a Claude Code session in the `rolec` repo.** It proves the already-built counsel-attestation flow works end-to-end on disposable data, and returns a go/no-go before any real lawyer link is issued. Near-zero code unless the dry run finds a gap.

---

```
TASK — ATT-1: Activate the counsel-attestation system end-to-end on a DISPOSABLE corridor (dry run),
before the first real lawyer link. No REAL prod requirement_items may change. Produce a go/no-go report.

WHY: the counsel-attestation feature is fully built and UNUSED (prod shows 0 corridor_attestation_requests).
Before a real lawyer sees it, prove the whole loop works and find any gaps. This is the trust moat
(why-not-ChatGPT; AIQ-1936/1937/1970).

WHAT EXISTS (read it first, do not rebuild):
- Backend: backend/app/routers/attestation.py — admin_router (/api/admin/attestations: create, list, get,
  send, promote) + public_router (/api/public/attestations/{token}: get, decide item, sign).
  backend/app/services/attestation_tokens.py (mint_token, hash_token, content_hash — canonical SHA-256).
- Frontend: frontend/src/pages/admin/AdminAttestationsPage.tsx, frontend/src/pages/public/AttestationReviewPage.tsx
  (route /attest/:token, public by design), frontend/src/api/attestation.ts, the "Counsel-attested" badge in
  frontend/src/components/requirements/RequirementList.tsx.
- Tables: corridor_attestation_requests / corridor_attestation_items / corridor_attestation_signatures.
- THE TWO-KEY RULE: the public token path only writes items + signatures; ONLY the admin `promote` writes
  requirement_items.attestation_status='attested', and only if the signature's signed_content_hash still
  equals the request's content_snapshot_hash. Preserve this — do not weaken it in ATT-1.

STEPS (run against local/staging DB or a clearly disposable test corridor — NEVER against real approved rows):
1. RECON + existing tests. Read attestation.py + attestation_tokens.py + the two FE pages. Run the existing
   tests (pytest backend/tests -k attestation, incl. the PII-boundary test; and the FE AttestationReviewPage /
   RequirementList.attestation tests). Report pass/fail. If any fail on a clean origin/main, say so (pre-existing).
2. SEED a throwaway corridor: insert 2–3 requirement_items with country_code='ZZ_TEST', purpose='employment',
   review_status='approved', a legal pillar (e.g. RESIDENCE), citations_json carrying a source_url, all tagged
   for teardown. (Disposable key so nothing real is touched.)
3. ADMIN create: POST /api/admin/attestations {country_code:'ZZ_TEST', purpose:'employment'}. Capture request id,
   raw review_token, review_url, content_snapshot_hash. Confirm items were snapshotted (claim/source/evidence)
   and the raw token is returned exactly once.
4. SEND: POST /api/admin/attestations/{id}/send → status 'sent'.
5. SIMULATE THE LAWYER (public path): GET /api/public/attestations/{token} → renders the checklist, NO PII.
   POST /{token}/items/{item_id} for each item — mix of 'approved' plus one 'amended' (to exercise
   changes_requested). POST /{token}/sign with agreed_to_disclaimer=true and the current content_hash →
   status 'signed', one signature row exists.
6. NEGATIVE CHECKS (all must hold): a malformed/expired token → 404 (same body as any miss); sign with a stale
   content_hash → 409; promote before sign → 409.
7. PROMOTE: POST /api/admin/attestations/{id}/promote → ONLY 'approved' items get
   requirement_items.attestation_status='attested' (amended/rejected skipped); the partial-write guard holds;
   attested_by / attested_at / latest_attestation_request_id set.
8. FE RENDER: load /attest/{token} and /admin/attestations (browser or FE test harness) and confirm the reviewer
   page and admin console render the seeded request end-to-end; confirm the "Counsel-attested" badge shows on an
   attested row and renders as ABSENT on a non-attested one.
9. TEARDOWN: delete the ZZ_TEST corridor_attestation_* rows + the seeded requirement_items; confirm the test
   batch is back to 0.
10. REPORT (go/no-go): does the built flow work end-to-end? List any gaps (broken endpoint, missing FE wiring,
    a needed migration). If GREEN → we can issue the first REAL request for country_code='IRELAND',
    purpose='employment' — AFTER the 6 ES→IE EEA rows are approved (see the counsel worklist). If RED → the exact
    fix as an ATT-1a follow-up (branch + PR, do not merge).

GOVERNANCE: disposable/staging data only; never attest or promote a REAL approved prod row in this dry run;
the first real IRELAND/employment request is a separate, human-initiated step. Any code fix goes on a branch +
PR — do not merge to main. Keep check_serving_llm_isolation and check_route_auth green.

REPORT BACK to Romain: test results, the 10-step outcome, and the one-line go/no-go.
```

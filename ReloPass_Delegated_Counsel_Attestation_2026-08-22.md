# ReloPass — Delegated Counsel Attestation: Activate + Extend to Cases

**Date:** 2026-08-22 · **Author:** Claude (Cowork) · **Owner:** Romain
**Trigger:** Romain's ask — a dedicated channel to delegate validation power to a third-party approver (lawyer/tax advisor), who accepts access, approves items, and **stamps** them (signed PDF / e-signature), where receipt of the stamp **auto-triggers case validation**, integrated into the admin.
**Finding:** this is already ~90% built in `rolec` and has **never been used**. Your ask is mostly an *activation + a small extension*, not a build.

---

## 0. TL;DR

There is a complete **Counsel Attestation** subsystem in the repo — backend router, crypto, three DB tables, the lawyer-facing reviewer portal, the admin console, the "Counsel-attested" badge, and tests. Prod shows **0 requests / 0 items / 0 signatures**: it shipped and was never switched on. It already does the hard, security-critical things you described — a tokenized no-account channel, per-item approve/amend/reject, an immutable credentialed signature under a real legal disclaimer, and a content-hash that voids the stamp if the checklist changes. What it does **not** yet do is the three things that turn it from a *trust layer* into the *delegated validator* you want: drive validation on signature (auto-trigger), attest a **case** (not just a corridor), and emit a **signed-PDF/e-sign** stamp. This doc inventories what's built, names the one design decision that "delegating power" hinges on, and phases the rest — starting with switching it on for ES→IE this week at near-zero code.

---

## 1. What's already built (verified in code + prod)

| Component | Where | What it does | State |
|---|---|---|---|
| Request/items/signature tables | `corridor_attestation_requests` · `_items` · `_signatures` | the request, the per-item decisions, the immutable signature | exist · **0 rows** |
| Admin API | `backend/app/routers/attestation.py` `/api/admin/attestations` | create (snapshot + mint token), list, get, send, **promote** | built |
| Public API | same file `/api/public/attestations/{token}` | view checklist, decide item, **sign** — token-scoped, rate-limited | built |
| Token/hash/content crypto | `backend/app/services/attestation_tokens.py` | 256-bit token, **hash-only storage**, canonical **content_hash** | built |
| Lawyer portal | `frontend/.../pages/public/AttestationReviewPage.tsx` `/attest/:token` | no-account reviewer view, decide + sign | built |
| Admin console | `frontend/.../pages/admin/AdminAttestationsPage.tsx` `/admin/attestations` | request a review, track it, promote the result | built |
| Mover-facing badge | `RequirementList.tsx` → `attestationBadge` "Counsel-attested" | shows the stamp as a trust signal, absent renders as absence | built |
| Tests | `AttestationReviewPage.test.tsx`, `RequirementList.attestation.test.tsx`, PII-boundary test | guardrails | built |

**The security model it already enforces (don't rebuild — inherit):**
- **Two-key rule.** The public link can *only* write `corridor_attestation_items` + `_signatures`. It never touches `requirement_items`. Turning an opinion into served content is a separate `require_admin` **promote** — the one place in the codebase that writes `attestation_status='attested'`.
- **Content-addressed stamp.** `content_hash()` is a canonical (sorted, fixed-separator) SHA-256 of a **whitelisted** checklist. `sign` rejects a hash mismatch (409); `promote` refuses if the signature's hash ≠ the request's snapshot hash. Edit the checklist after signing and the stamp is void by construction — this is versioning + tamper-evidence for free.
- **Real legal stamp.** The signature row is immutable and carries `signer_name/org/credential`, `signature_method`, `signed_content_hash`, the frozen `signed_payload_json`, `disclaimer_version/text`, `signed_ip/user_agent`, `supersedes_signature_id`, `signed_at`. The disclaimer explicitly says a qualified professional reviewed it and "ReloPass may rely on and retain this as evidence of professional review."
- **Channel hygiene.** Raw token shown once, never stored (hash-only); constant-time compare; every miss returns the same 404 (enumeration-proof); strict PII whitelist on the public payload; per-route rate limits; 30-day TTL.

This is genuinely good work. It is the spine of the trust moat (cards 1936/1937/1970) — sitting dark.

---

## 2. Your vision → what's built vs. the gap

| You said | Built? | Detail / gap |
|---|---|---|
| "a dedicated channel I provide to a lawyer, they accept access" | ✅ | `/attest/:token` — tokenized, no account, public by design |
| "accept the different things" | ✅ | per-item `approved` / `amended` / `rejected` + comment + proposed amendment |
| "which will validate and stamp" | ✅ | `sign` → immutable credentialed signature under the disclaimer |
| "PDF signed or other forms of approval" | ◑ | `signature_method` + `signed_payload_json` exist; **signed-PDF cert + e-sign/QES not generated yet** |
| "get validation for a **case**" | ✗ | system is **corridor-scoped** (`country_code`+`purpose`); no case scope |
| "receive the approval, **trigger the validation automatically**" | ✗ | promote is a **manual admin second key**; no auto-advance on signature |
| "when within the admin we try to get validation… everything in place to send it" | ◑ | admin can create/send a **corridor** request; not wired to a "validate this case" action |
| deliver the link to the lawyer | ✗ | admin gets the raw URL once and shares it manually; no email/registry |

---

## 3. The one decision "delegating power" hinges on

Today, attestation is a **second, orthogonal axis** on top of your internal approval — the code and the frontend are emphatic about it (`attestationStatus` is "a SEPARATE axis from verificationStatus, not a further rung"). Two independent gates:

- **`review_status`** `pending → approved` — *your* internal call (the `/admin/countries` click). **This is what controls whether a row serves.**
- **`attestation_status`** `→ attested` — the *external counsel* stamp. A trust/liability layer. **It does not currently control serving.**

So right now a lawyer can only *confirm what you already approved*. Your ask — "dedication of power to a third party… trigger validation automatically" — wants counsel able to **drive** validation. That's the decision:

> **Does a signed counsel attestation stay a trust layer on top of your approval, or become a primary validator whose signature advances what serves?**

**Recommendation: make it configurable, safe-by-default.** Add a per-request `promotion_policy`:
- `manual` (default) — today's two-key behaviour; nothing auto-serves. Right for the first corridors and for anything high-risk.
- `auto_on_sign` — a signed, hash-matching attestation from a credentialed reviewer **auto-promotes** the approved items (and, if you opt in, advances `review_status → approved` for items you sent as pending). Still enforces hash-match + approved-only + full audit; still refuses partial writes.

This gives you real delegation where you choose it, keeps the safety rail as the default, and never removes the human option. It is the smallest change that turns the built system into the one you described.

---

## 4. Phased plan

**Phase 1 — ACTIVATE for ES→IE (this week, near-zero code).** Switch the built feature on with its first real corridor.
1. Approve the 6 EEA rows internally at `/admin/countries` (your judgement they're representative + sourced) — see the companion `ReloPass_ES-IE_Counsel_Review_Worklist_2026-08-22.md`.
2. From `/admin/attestations`, create a request for `IRELAND / employment` (the built `create_attestation` snapshots the approved legal-pillar rows, excludes HOUSING/TIMELINE, mints the token).
3. Send the link to a real lawyer; they decide each item and sign; you `promote`. First **Counsel-attested** corridor on the board — the trust signal now renders to movers.
   - *Pre-flight:* confirm the reviewer FE renders end-to-end (backend is proven by tests; the page exists — do one dry run against a staging token), and decide link delivery (manual paste is fine for #1).

**Phase 2 — DELEGATION extension (the "dedication of power" model).**
- `promotion_policy: manual | auto_on_sign` (§3).
- Allow a request to include `pending` rows and advance `review_status → approved` on counsel approval, so counsel can be the *primary* gate where you choose.
- Link **delivery**: email the reviewer the link on `send`; a small **counsel registry** (reviewer identities + credentials) so you pick a firm instead of retyping.

**Phase 3 — CASE scope + auto-trigger (your exact "validate this case" flow).**
- A **case-scoped** attestation request: snapshot a specific case's served roadmap/requirements (reusing the same tables with a `case_id` scope).
- On signature, **auto-advance the case**: set `roadmap_review_status.released_to_user = true` — reusing the existing case-release mechanism already read by `roadmap_confidence_gate.py`. No new release path, just a new trigger for it.
- Wire the admin case view: **"Request validation"** → assemble snapshot → send to counsel → receive signature → release the case automatically. That is precisely "we get everything in place to send it, receive the approval, trigger the validation for case automatically."

**Phase 4 — Richer stamps (legal-grade, long-run).**
- Generate a **signed-PDF certificate** from `signed_payload_json` (the frozen decisions + disclaimer + signer + hash) — a human-readable, retainable artifact of the attestation.
- `signature_method` → integrate **e-signature / QES** (DocuSign, or eIDAS Qualified Electronic Signature for EU legal weight) for non-repudiation beyond typed-name.

---

## 5. Governance (preserve the spine you already built)

- **Two-key stays the default.** `auto_on_sign` is explicit, per-request opt-in and still enforces: request `signed`, signature hash == snapshot hash, only `approved` items promoted, no partial write, credentialed signer, full audit.
- **Content-hash binding already voids stale stamps** — an edit after signing forces re-attestation. Wire this to a **stale downgrade**: on content change, set `attestation_status='stale'` (the FE type already has `'stale'`!) so a decayed stamp reads as absence, not reassurance. This is the re-verification engine (card 1973) + versioning (card 1959) meeting attestation.
- **Serving still reads approved-only.** The counsel stamp is provenance the mover sees ("Counsel-attested") — the concrete answer to "why not just use ChatGPT?" (cards 1970/1969), now backed by a named professional's signed, retained attestation.

---

## 6. Proposed AIQ cards (the gap, as executable intent)

| id | card | layer / entry points | tier |
|---|---|---|---|
| **ATT-1** | Activate counsel attestation for ES→IE (first live corridor) | ops + `/admin/attestations` + `/attest/:token` dry run | 🟡 |
| **ATT-2** | `promotion_policy: manual\|auto_on_sign` + allow-pending + advance `review_status` on counsel approval | `attestation.py` promote/create; `requirement_items` | 🔴 (changes what serves) |
| **ATT-3** | Case-scoped attestation + auto-release on signature (wire `roadmap_review_status`) | `attestation.py`, `roadmap_confidence_gate.py`, case admin view | 🔴 |
| **ATT-4** | Link delivery (email on send) + counsel registry | `attestation.py`, a `counsel_reviewers` table, notifications | 🟡 |
| **ATT-5** | Signed-PDF attestation certificate from `signed_payload_json` | new service (pdf), admin download | 🟡 |
| **ATT-6** | e-signature / QES `signature_method` integration | `attestation.py` sign path, provider adapter | 🔴 (legal) |
| **ATT-7** | Stale-attestation downgrade on content change | `attestation_status='stale'`; tie to change-detection (1973) | 🟡 |

These slot into the same Armed-Card contract and the same bridge/dev-queue flow as the corridor work. ATT-2 + ATT-3 are the heart of your vision; ATT-1 proves the channel end-to-end first.

---

## 7. The immediate worklist

The companion file **`ReloPass_ES-IE_Counsel_Review_Worklist_2026-08-22.md`** is the counsel-facing checklist for the six ES→IE EEA rows + the one emergency-tax reconciliation — the exact content that becomes the first attestation request. It doubles as the doc you can hand a lawyer today, and as the snapshot for `create_attestation` when you switch the channel on.

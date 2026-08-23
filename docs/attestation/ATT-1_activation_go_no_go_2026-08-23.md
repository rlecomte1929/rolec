# ATT-1 — Counsel attestation: activation go/no-go

**Verdict: GO, with one gate that is not mine to close.**
Date: 2026-08-23 · Card: AIQ-2096 (P1, 🟡 Yellow) · Corridor: ES→IE

The subsystem is built, wired, guarded and live in production. Nothing in the code path
blocks switching it on. The remaining gate is that no ES→IE row has been approved by a
reviewer yet, and attestation is a step *after* approval — see §5.

---

## 1. What was verified, and how

Everything below is an observation, not a reading of the design doc.

| # | Claim | Evidence | Result |
|---|---|---|---|
| 1 | The feature is built and unused | `corridor_attestation_requests` / `_items` / `_signatures` all exist in prod, **0 rows each** | ✅ confirmed |
| 2 | Tests cover the flow | `pytest backend/tests -k attestation` → **78 passed, 1 skipped** | ✅ |
| 3 | Routers registered in BOTH apps | 4 `attestation` references in `backend/main.py` **and** 4 in `backend/app/main.py` | ✅ |
| 4 | Reviewer page is routed, not just declared | `App.tsx:321` mounts `ROUTE_DEFS.attestationReview` (`/attest/:token`) | ✅ |
| 5 | Admin page is routed, not just declared | `App.tsx:451` mounts `adminAttestations` behind `RequireAdminRoute` | ✅ |
| 6 | Bad token → 404 | `GET https://api.relopass.com/api/public/attestations/deadbeef…` → **404** | ✅ |
| 7 | Admin API is guarded | `GET /api/admin/attestations` unauthenticated → **401** | ✅ |
| 8 | ATT-3 case scope is applied to prod | `corridor_attestation_requests.scope` (`'legal'`) and `.case_id` both present | ✅ |
| 9 | No prod requirement was touched | `requirement_items` with `attestation_status IS NOT NULL` → **0** | ✅ |

Checks 4 and 5 are not ceremony. A page that exists in `pages/` and is named in
`routes.ts` but never mounted as a `<Route>` is a dead surface, and that has shipped in
this repo before. Both are genuinely mounted.

## 2. The two-key rule is CONDITIONAL, and the card does not say so

The card states it as an invariant: *"the token path only writes items+signatures; only
admin `promote` writes `attestation_status='attested'`."*

That was true when the card was written. `_maybe_auto_promote`
(`attestation.py:773`, from ATT-2.4) now lets a signature publish directly, and the card
does not mention it. It is **not a defect** — it is an opt-in waiver with four required
conditions, and it reuses `_apply_promotion` rather than reimplementing the gates:

* `promotion_policy == 'auto_on_sign'`, recorded at creation
* the signer supplied a `signer_credential` (an anonymous typed name is recorded but may
  not publish)
* every `_apply_promotion` gate passes, content-hash check included
* the item is `approved` — `amended` / `rejected` are skipped

**The reason this is safe is the default, so the default was checked rather than assumed:**

```
promotion_policy       NOT NULL  DEFAULT 'manual'
advance_review_status  NOT NULL  DEFAULT false
scope                  NOT NULL  DEFAULT 'legal'
status                 NOT NULL  DEFAULT 'draft'
```

Every existing and future request is `manual` unless someone deliberately asks otherwise.
Had that default been `'auto_on_sign'`, every signature would publish straight to the
served catalog — which is why it is recorded here as a measured fact.

**Action: correct the card's wording, not the code.**

## 3. Not proven, and why

The full **create → send → public view → decide → sign → promote** round trip was not
executed. It needs writes, and there is no staging database — the only place to run it is
production, against a disposable corridor with teardown.

The card authorises exactly that ("staging/disposable data only; teardown deletes the test
corridor + attestation rows"). It was not done unattended because a create/promote cycle
touches the same tables the real first attestation will use, and a failed teardown leaves
a fake corridor review in the audit trail of a compliance feature. It is a five-minute
supervised run, not a risk — it just wants a human present.

What the 78 tests already prove about that path: item decisions, signing, the stale
`content_hash` → 409, promote-before-sign → 409, and approved-only promotion with no
partial write. The untested delta is real infrastructure — token generation, email
delivery of the link, and the browser render at `/attest/:token`.

### Exact steps for the supervised run

```bash
# 1. create against a throwaway corridor (NOT ES/IE)
POST /api/admin/attestations         {corridor: "ZZ→ZZ", ...}     # promotion_policy defaults to 'manual'
# 2. send, and copy the token from the response
POST /api/admin/attestations/{id}/send
# 3. open /attest/:token in a logged-OUT browser — confirm it renders and shows no PII
# 4. decide a MIX (at least one approved and one amended), then sign
POST /api/public/attestations/{token}/items/{item_id}
POST /api/public/attestations/{token}/sign
# 5. negative checks
GET  /api/public/attestations/bogus                    -> expect 404   (already verified in prod)
POST .../sign with a stale content_hash                -> expect 409
POST /api/admin/attestations/{id}/promote  before sign -> expect 409
# 6. promote, and confirm ONLY the approved item flipped
POST /api/admin/attestations/{id}/promote
# 7. teardown — delete the request, its items, its signatures, and the throwaway corridor
```

## 4. Gaps found

1. **Card wording drift** (§2) — the two-key rule is now waivable. Fix the card.
2. **No prod-side alert on `auto_on_sign`.** The waiver is safe by default, but nothing
   surfaces that a request was created with it. A request that auto-publishes looks
   identical afterwards to one an admin promoted. Worth a follow-up: record the policy on
   the admin list view so a reviewer can see which requests can self-publish.

Neither blocks activation.

## 5. The actual gate — and it is not code

Ireland has **65** rows in `requirement_items`: **29 approved, 36 pending**. Zero carry any
`attestation_status`.

Attestation is a step *after* human approval — a counsel signs off on what the catalog
already asserts. The card's own Dependencies say real launch "needs the 6 ES→IE EEA rows
approved first (see `ReloPass_ES-IE_Counsel_Review_Worklist_2026-08-22.md`)".

So the sequence is: approve the ES→IE EEA rows → run the supervised dry run above →
send the first real IRELAND/employment lawyer link. Steps 2 and 3 are ready now; step 1 is
a human review that has not happened.

## 6. Recommendation

**GO on the system.** Do not send a real lawyer link until the supervised dry run in §3 has
been run once and the ES→IE rows in §5 are approved. Fix the card wording in §2 regardless,
because a stated invariant that is no longer strictly true is how a reviewer ends up
trusting the wrong thing.

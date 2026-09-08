# RUN 004-W — Consolidated verification of the deployed fixes

**Target:** relopass.com / api.relopass.com · **Expected prod commit:** `1ca6061f` (main HEAD).
**Two lanes, both required for a PASS:** **Audos** drives the browser + shell (`curl`); **Cowork** runs the DB half via the Supabase MCP (`execute_sql`, project `nsvefcvpvwwwhuqyuqmp`). A fix is "verified" only when browser + DB agree.

This pass verifies six things that landed since prod was on `a8bc353f`:
RFQ dispatch loop (#1670/#1688), NL_SG movers cap (#1689), paywall buy-button (#1691), services-state persist (#1682), and the **cross-tenant IDOR fix (#1679)**.

---

## SEGMENT 0 — deploy gate (MANDATORY, do first)

**Tool: Audos shell (`curl`).**
```bash
curl -s https://api.relopass.com/health
```
**PASS only if** `"commit":"1ca6061f…"`. If it still shows `a8bc353f` (or anything older), **STOP** — the deploy didn't land; everything below would test stale code. Report the commit you see.

---

## SEGMENT 1 — ⭐ RFQ dispatch loop, end to end (the prize)

The read + dispatch id bugs are both fixed (`coordinationCaseId` now feeds the dispatch panel). This is the loop we could never complete.

**Tool: Audos shell to mint, Audos browser to drive, Cowork `execute_sql` to confirm.**

**Mint (Audos `curl`):**
```bash
curl -sX POST https://api.relopass.com/api/test-drive/provision-staged \
  -H 'Content-Type: application/json' \
  -d '{"first_name":"R4w1","campaign":"qa-r4w1","corridor_id":"FR_NO","stage":"shortlist_ready"}'
```
Record `case_id`, `assignment_id`, and both credential sets from the JSON.

**Audos browser — one fixture per browser session, type by keyboard, PageDown for inner scroll, click custom controls by coordinate:**
1. **Employee** (fresh session): Services → Request quotes → submit all 6 vendors. Confirm "Request recorded" (inbox-framed).
2. **HR** (separate fresh session): open the case detail.
   - ⭐ **"Vendor quote requests" panel** lists the RFQ with **6 vendors** (the read — already proven, re-confirm).
   - ⭐ **The dispatch surface now shows the RFQ + a Dispatch control** (this is the #1670 dispatch fix — previously empty). **Click Dispatch** (leave email OFF / inbox-only).
   - ⭐ After dispatch, a **supplier magic link appears in the in-app inbox** (NOT emailed). Copy it.
3. **Supplier** (clean signed-out context): open the magic link → submit a quote (amount `1234`, note `QA R4W1`). Confirm.
4. **HR** again → the **quote appears / links to the quote-review page**.

**Rules:** never `insead-2026` · never set `OUTBOX_DISPATCH_CRON_ENABLED` · **no real email** (hard guard — if a real outbound email fires, 🔴 stop) · approve no supplier records · if any step blocks, report exactly where and stop (BLOCKED ≠ FAIL).

**Cowork DB (`execute_sql`) — run after Audos reports, with the case_id:**
```sql
-- rfq + recipients + tokens + dispatch signal + quote + resend
WITH c AS (SELECT '<CASE_ID>' AS cid)
SELECT
  (SELECT count(*) FROM rfqs r,c WHERE r.case_id::text=c.cid)                                                       AS rfqs,
  (SELECT count(*) FROM rfq_recipients rr JOIN rfqs r ON rr.rfq_id=r.id,c WHERE r.case_id::text=c.cid)              AS recipients,
  (SELECT count(*) FROM rfq_recipients rr JOIN rfqs r ON rr.rfq_id=r.id,c
     WHERE r.case_id::text=c.cid AND rr.status='dispatched')                                                        AS recipients_dispatched,
  (SELECT count(*) FROM notification_outbox WHERE payload::text ILIKE '%'||(SELECT cid FROM c)||'%')                AS outbox_rows,
  (SELECT count(*) FROM quotes q JOIN rfqs r ON q.rfq_id=r.id,c WHERE r.case_id::text=c.cid)                        AS quotes;
```
**PASS criteria (browser + DB agree):**
- Dispatch button present and click returns `dispatched=6` (browser) → DB `outbox_rows > 0` (dispatch created the inbox notification) and recipient status advances.
- Supplier submit → DB `quotes ≥ 1`.
- **Zero Resend log entries** (inbox-only; `send_email=false`). Cowork confirms no Resend send + `outbox` rows are inbox-typed, not email-sent.
- If the supplier magic link is cron-gated and doesn't surface without `OUTBOX_DISPATCH_CRON_ENABLED`, that is a **finding** (report it) — do NOT enable the cron.

---

## SEGMENT 2 — NL_SG movers no longer silently capped (#1689)

**Tool: Audos browser + Cowork `execute_sql`.**

**Mint (Audos):** `corridor_id":"NL_SG"`, `stage":"shortlist_ready"`, `campaign":"qa-r4w2"`.
**Audos browser:** employee → Recommendations → **movers category** → count the movers actually rendered (use PageDown to see the full list).
**PASS:** rendered movers == distinct vetted movers seeded (expect ~12, not 10). No silent drop; if a "show more / hidden by cap" affordance exists, it reveals the rest.

**Cowork DB — seeded vs the known render cap:**
```sql
SELECT count(*) AS movers_seeded,
       count(DISTINCT master_item_id) AS distinct_masters
FROM <the movers-seeding table for the case>   -- reuse the RUN-004 Segment-A query, keyed on <CASE_ID>
;
```
**PASS:** browser rendered count == distinct_masters (no gap), OR any excluded master has a logged reason.

---

## SEGMENT 3 — Paywall: no buy button after payment (#1691) 🔴 test-mode only

**Tool: Audos browser (test card ONLY) + Cowork `execute_sql`.**

**Mint (Audos):** `stage":"roadmap_ready"`, `corridor_id":"FR_NO"`, `campaign":"qa-r4w3"`.
**Audos browser:**
1. Unpaid case → roadmap is gated (paywall shows).
2. Complete checkout **using ONLY the on-screen test card** (test-drive mode surfaces it). **Never a real card.** If a real-card field appears with no test instructions → stop, that's the finding.
3. After return: the **buy button is gone**, the roadmap unlocks, and there is **no infinite loading spinner** on `?payment=success`.
4. Reload the roadmap by direct URL (case id AND assignment id) → stays unlocked for the paid case; a *second unpaid* case still gates.

**Cowork DB:**
```sql
SELECT id::text, access_tier FROM relocation_cases WHERE id::text = '<CASE_ID>';
-- PASS: access_tier flipped 'free' → 'roadmap' after the test payment; no duplicate entitlement on webhook retry.
```

---

## SEGMENT 4 — services-state persists 6/6, zero 400s (#1682)

**Tool: Audos browser + Cowork `execute_sql`.**

**Mint (Audos):** `stage":"roadmap_ready"`, `corridor_id":"FR_NO"`, `campaign":"qa-r4w4"`. (Start pre-shortlist so you exercise the Add-to-package writes.)
**Audos browser:** employee → add **6 items** to the package in quick succession. **Expect zero 400s** on "Add to package"; "Request quotations" enables and routes to `/services/rfq/new`. (If a transient CORS/500 blip appears, one "Try again" is allowed — a persistent 400 is the finding.)

**Cowork DB (shortlist is CATEGORY-KEYED — count item ids, not array length):**
```sql
SELECT jsonb_array_length(state_json->'shortlist') AS categories,
       (SELECT count(*) FROM jsonb_array_elements(state_json->'shortlist') cat,
               jsonb_array_elements(cat->1) ids)     AS total_item_ids
FROM services_state WHERE case_id::text = '<CASE_ID>';
-- PASS: total_item_ids = 6 (regardless of categories). This is the mistake I made in RUN 004-B — do NOT read categories as the item count.
```

---

## SEGMENT 5 — 🔒 Cross-tenant IDOR fix (#1679) — HIGHEST-VALUE security check

`GET /api/cases/{id}/messages` was returning another tenant's messages. Verify it now **403s cross-tenant**.

**Tool: Audos shell (`curl`) — the cleanest way; needs two tenants.**

1. Mint **two** fixtures in **different campaigns** (distinct companies):
   ```bash
   curl -sX POST .../provision-staged -d '{"first_name":"R4wA","campaign":"qa-r4w5a","corridor_id":"FR_NO","stage":"case_created"}'
   curl -sX POST .../provision-staged -d '{"first_name":"R4wB","campaign":"qa-r4w5b","corridor_id":"FR_NO","stage":"case_created"}'
   ```
   Record tenant A's HR token (from login) and tenant **B's** `case_id`.
2. Sign in as A's HR to get a bearer token, then:
   ```bash
   curl -s -o /dev/null -w '%{http_code}\n' \
     -H "Authorization: Bearer <A_HR_TOKEN>" \
     https://api.relopass.com/api/cases/<B_CASE_ID>/messages
   ```
**PASS: `403`** (or `404` no-existence-leak). **FAIL (🔴 critical, report first): `200`** with B's data.

**Cowork** cross-checks the authorization exists in code (already confirmed: #1679 added the tenant guard) and can run a DB sanity check that the two cases belong to different `company_id`s.

---

## Report block (Audos, per segment)
```
RUN 004-W · SEG __ · DATE ____ · CAMPAIGN qa-r4w_ · CORRIDOR ____
PROD COMMIT (seg 0): ____   MINT http ____
BUDGET __/50   VERDICT: PASS / FAIL / BLOCKED
WHAT I OBSERVED (facts): ____
🔴 CRITICAL (report first, stop): ____
FOR COWORK — DB: case ____ assignment ____   ARTIFACTS: qa-r4w_
```

## Sequence
0 (deploy gate) → **1 (RFQ loop)** and **5 (IDOR)** first — the two that matter → 2, 3, 4 as spot-checks. One segment per browser session; mint fresh each time. Cowork runs the DB half after each Audos report; both lanes must agree.

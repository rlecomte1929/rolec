# ReloPass RFQ: what exists, what is missing, what to be careful about

Grounded in `origin/main` (commit `ba6226f2` live on api.relopass.com at 2026-09-12 16:45 UTC) and a live probe run as HR (hr@testingapril.com) against RFQ `RFQ-20260714-ac4afa91`.

## 1. Verdict in one paragraph

The RFQ plumbing is solid (token minting, guards, supplier page, HR validation), but **no email reaches anyone today** and **no notification of any kind fires on quote events**. Suppliers get a link only inside the employee's in-app inbox. The employee is not told when a quote arrives, HR is not told when quotes are ready, suppliers are not told whether they won. The structure is there; the messaging layer is missing. That is what to build next.

## 2. What actually happens today (verified)

| Step | What the code does | Email? |
|---|---|---|
| Employee sends RFQ (`POST /api/rfqs`, `backend/main.py:9266`) | Creates `rfqs` + `rfq_recipients`, mints one magic-link token per supplier via `dispatch_supplier_links` | **No.** Mode is `inbox` unless feature flag `SUPPLIER_RFQ_EMAIL_ENABLED` is on. Link is posted as a `quote_messages` row in the employee's Vendors thread. |
| HR "Email suppliers" (`POST /api/hr/rfqs/{id}/supplier-links`, `supplier_rfq.py`) | Same dispatcher, `send_email:true` selects email mode | **No, on prod.** Live probe returned `mode:"inbox"` even with `send_email:true` and an explicit address, which means `RELOPASS_SUPPLIER_EMAIL_LIVE` is OFF on Render. This hard gate sits above every other switch. |
| Supplier opens link (`GET /api/supplier/rfq`) | Marks recipient `viewed` | No notification to anyone. |
| Supplier submits (`POST /api/supplier/rfq/quote`) | Creates `quotes` + `quote_lines`, marks recipient `replied`, logs one line | **Nothing.** No `create_notification_with_preferences`, no outbox row, no `quote_received` analytics event (that event only fires on the dead `require_vendor` route). Employee and HR find out only by opening the page. |
| Employee proposes (`PATCH .../propose`) | Sets `preferred_quote_id` | Nothing. |
| HR validates (`PATCH .../accept`, `validate_rfq_quote` in `db/vendors.py`) | Accepts one, rejects siblings, closes RFQ, writes cost to `case_services` | **Nothing** to employee, winner, or losers. Supplier "thank you" page promises "the company will be in touch", which nobody is prompted to do. |
| Reminders / expiry | `respond_by` = invited_at + 7 days, token expires at 14 days | No reminder job, no expiry notice, no "no response" alert to HR. |

Supporting facts:
- Supplier email guards (`supplier_link_dispatch.py`): needs `suppliers.contact_email`, `verified=true`, not a personal webmail domain (`gmail/hotmail/outlook/yahoo/icloud/proton`), and the actor must not be `@probe.test` / `@testco.com`. HR typing an address counts as verification.
- Employee/HR email notifications use a different pipe: `notification_outbox` drained by `POST /api/crons/dispatch-outbox`, with a recipient allowlist `RELOPASS_OUTBOX_ALLOWED_DOMAINS` defaulting to `@probe.test` only. So even after you add quote notifications, **real employees will not get email until that allowlist is widened**.
- Two Resend senders exist: backend `_resend_send` (`assignment_invite_email.py`, from `EMAIL_FROM` default `noreply@relopass.com`) and a Supabase edge function `send-notification-email` (from `notifications@relopass.com`, provider defaults to `stub`). Pick one sender for the RFQ pack; two "from" addresses on one thread looks like spoofing to a vendor.
- Whether `RESEND_API_KEY` is set on prod is **not confirmed**: the only probe is admin-only (`GET /api/admin/email-smoke-test`, sends to the admin's own address). Run it once from an admin session.
- The brief is only structured for `movers` (`rfq_brief.build_movers_requirements`). Housing, schools, banks, insurance, temp accommodation all reach the supplier as a single "Details: Not specified" row. Subject line only carries the route for movers.
- Supplier page (`SupplierQuotePage.tsx`): asks the vendor to "flag anything you need that is missing" but has **no field** for it; no "I cover this route / can meet the date" confirmation even though the email asks for it; no supplier contact name/phone captured; currencies limited to EUR/GBP/USD/NOK/SGD/AED; analytics consent dialog fires on a vendor with no account; page title is the marketing tagline.
- HR view shows the vendor as `vc-<uuid>` not its name, lists raw item JSON, and cap comparison refuses multi-service RFQs (from the 2026-09-12 dry run).

## 3. Test result: can I confirm emails land in an inbox?

Not yet, and not from here:
- Supplier emails cannot land anywhere while `RELOPASS_SUPPLIER_EMAIL_LIVE` is off (confirmed live).
- Employee/HR emails cannot land at any domain other than `@probe.test` while the outbox allowlist is at its default.
- I have no readable test inbox in this browser session (no Google account signed in, Outlook not signed in). A Gmail or a Resend test address you can open is needed for the inbox check.

The safe test sequence, once you want to run it, is in the Otto test matrix (brief 3). Short version: staging first with `RELOPASS_SUPPLIER_EMAIL_LIVE=true`, `SUPPLIER_RFQ_EMAIL_ENABLED=true`, `RELOPASS_OUTBOX_ALLOWED_DOMAINS=@relopass.com,@<your test domain>`, a supplier row whose `contact_email` is your test inbox and `verified=true`, and an HR actor whose email is not on a seeder domain.

## 4. Things to be careful about (the ones specific to this design)

1. **Two gates plus a flag plus a key.** Turning supplier email on requires all of: `RELOPASS_SUPPLIER_EMAIL_LIVE=true`, feature flag `SUPPLIER_RFQ_EMAIL_ENABLED=true` (DB row wins over env), `RESEND_API_KEY`, and a verified non-webmail address on the supplier row. Miss one and it silently falls back to inbox; the employee sees "HR will follow up" copy. Add an admin "email readiness" panel that shows all four.
2. **Personal-domain guard will block your own tests.** Testing with `romain_lecomte@hotmail.com` as a supplier is refused by design. Use a custom-domain test inbox or a Resend test address.
3. **Re-sending rotates the token.** `_mint_link` overwrites `token_hash`; the old link dies. If HR clicks "resend" after a vendor already opened the first email, the vendor's first link 401s with "This link is no longer valid". The resend email must say "use this newer link".
4. **Only the token hash is stored.** If the inbox message write fails (it is best-effort), the link is unrecoverable; you must re-mint. Log the mint outcome per recipient.
5. **No idempotency on RFQ create.** A client retry creates a second RFQ and re-dispatches. Add an idempotency key (case_id + sorted vendor ids + items hash, 5 min window).
6. **No notifications on supplier submit** means adding them touches `supplier_rfq.submit_supplier_quote`, which currently has no user context (supplier has no account). Resolve employee and HR recipients from `rfqs.case_id` -> `case_assignments` -> users, and enqueue via `create_notification_with_preferences` so preferences are respected.
7. **HR validation has no side-channel to suppliers.** The "won" email needs a reply-to that reaches the payer (HR) or the employee, otherwise the supplier cannot "be in touch". Decide reply-to per audience before templating (Otto's pack includes a `reply_to_policy` field for this).
8. **Data minimisation.** The supplier email body includes employee free text (`special_items`, `notes`). It is HTML-escaped (good) but not screened for personal data. Add a soft warning on the employee form: "this text is sent to suppliers".
9. **Deliverability.** Confirm SPF/DKIM/DMARC for relopass.com in Resend and register bounce/complaint webhooks; a bounced supplier should flip the recipient to `not_contacted` and notify the employee, otherwise the RFQ waits 7 days for a vendor who never got it.
10. **Multi-service RFQ mismatch.** One RFQ can bundle 4 services, but a mover cannot price housing. Either dispatch per service (one recipient sees only its service item) or state clearly in the email which item(s) they are asked to price. The comparison/cap code already refuses mixed RFQs, so per-service dispatch is the cleaner fix.
11. **Timezones.** `respond_by` is computed in UTC date and rendered as an ISO date string in three places. Fine for now, but say "end of day, Europe/Dublin" or similar once you send to vendors.
12. **Outbox allowlist default.** Widen it per customer domain, never `*`. First real customer: `RELOPASS_OUTBOX_ALLOWED_DOMAINS=@probe.test,@relopass.com,@<customer-domain>`.

## 5. Otto (Audos) deliverables and what I checked

All three were produced by Otto from standalone briefs (saved alongside), extracted from the chat DOM, parsed, and validated by script. Otto cannot see the repo, so every fact in the briefs came from the code read in section 2.

| File | What it is | Validation result | Fixes applied / open |
|---|---|---|---|
| `rfq_email_pack.json` | 10 transactional templates (5 supplier, 3 employee, 2 HR), subject/preheader/text/html, triggers, `do_not_send_when`, fallbacks, sequence timeline | 0 errors, 7 warnings (empty `do_not_send_when` on 6 always-send templates, 1 preheader > 90 chars). Every `{{variable}}` is in the allowed list; supplier templates use no employee/company identity; no compliance claims; no `<style>/<script>`; `<script>` in a brief value renders escaped in my sample render. Otto's first stream restarted mid-JSON; I kept the complete second pass. | Open: (a) templates 3/4/5 give suppliers a "View your submission" CTA on `magic_link`, but `require_supplier_link` returns 409 after one submission, so the backend must allow a read-only GET after submit (or drop the CTA); (b) Otto softened ask 2 to "itemised breakdown helpful but not required", keep the repo's stronger `RESPONSE_EXPECTATIONS` wording; (c) `employee_rfq_sent` heading says "Services not covered" but `not_contacted` is per supplier, retitle "Suppliers we could not reach"; (d) add a fallback subject for unknown route (currently "(origin not confirmed) to (destination not confirmed)"); (e) `hr_quotes_ready` subject should carry the employee name and rfq_ref. |
| `rfq_quote_templates.json` | Per-service supplier quote form spec for 13 services: common header/coverage/contact fields, brief fields (case vs employee_answer), line-item template with unique codes and policy-cap mapping, extra fields, comparison keys, red flags, rendering rules | Delivered in 2 batches, merged. 76 unique line codes, all units valid, all brief sources valid, no identity fields, no claims. | Fixed: removed `company_policy_cap` from 6 supplier briefs (Otto copied it from my "known data" list; it must never reach a vendor). Open: schools/banks/insurance have no required line; 10 labels > 40 chars. |
| `rfq_test_matrix.json` | 2 environments with exact flag values and test inboxes, 22 test cases (17 P0) with actor-named steps, 12-step go-live checklist (10 blocking), 12 watch-outs | Every test names an actor; all 12 required coverage areas present; no claims. First attempt in the shared meeting was wiped twice by Audos; re-ran in a fresh meeting. | Note: the watch-out on the test-persona guard suggests an `is_test_user` column; the repo already has `is_test` on `profiles` (migration 20260629), so `looks_like_test_email` should read that flag as well as the suffix list. |

How the extraction works, for next time: Otto renders the answer in a `<pre>` element; `document.querySelectorAll('pre')[n].textContent` gives the raw JSON (innerText of the chat pane mangles it). If Otto restarts its stream, the block contains two json fences; take the last one. Big briefs (over ~40k chars of output) risk a wipe in a long meeting; batch them or use a fresh meeting.

## 6. Build plan (what to rebuild in the repo, now that the JSON is verified)

Phase A: notifications without email (safe today)
- `backend/app/services/rfq_notifications.py` (new): `notify_quote_received(rfq_id, quote)`, `notify_quotes_ready(rfq_id)`, `notify_quote_validated(rfq_id, quote_id)`, `notify_rfq_sent(rfq_id, contacted, not_contacted)`; each resolves recipients from the case and calls `db.create_notification_with_preferences` (in-app bell + outbox row when the user opted in).
- Wire: `supplier_rfq.submit_supplier_quote` -> `notify_quote_received` + emit `EVENT_QUOTE_RECEIVED`; `main.create_rfq` -> `notify_rfq_sent`; `main.accept_quote` -> `notify_quote_validated`.
- Tests: `backend/tests/test_rfq_notifications.py` mirroring `test_submit_notifies_hr.py`.

Phase B: templates
- `backend/app/services/rfq_email_templates.py`: load Otto's `rfq_email_pack.json` (checked into `backend/seed_data/`), render with `html.escape` on every variable, `{{brief_rows_table}}` / `{{quote_lines_table}}` / `{{not_contacted_table}}` rendered server-side. Replace the inline `rfq_email_html` in `supplier_link_dispatch.py` with `render('supplier_rfq_invite', ...)`.
- Supplier-facing sends (invite, reminder, ack, selected, closed) go through `_resend_send` directly (they are not users, so no preferences); employee/HR sends go through the outbox.
- Tests: `test_rfq_email_injection.py` extended to every template; snapshot test that `variables_used` is a subset of the allowed list.

Phase C: supplier form per service
- `backend/app/services/rfq_brief.py`: generalise `build_*_requirements` from Otto's `quote_templates.json` (`brief_fields` per service), keep "Not specified" rule.
- `SupplierQuotePage.tsx`: render `coverage_confirmation_fields`, `supplier_contact_fields`, service `quote_line_template` as pre-labelled lines, plus "what is missing" textarea; POST payload gains `covers_route`, `can_meet_date`, `missing_info`, `contact`, `line_code`.
- Migration: `quote_lines.code text null`, `quotes.covers_route bool`, `quotes.can_meet_date bool`, `quotes.missing_info text`, `quotes.supplier_contact jsonb`. Follow the migration numbering rule (above both max file on main and max ledger version).

Phase D: reminders and no-response
- `POST /api/crons/rfq-reminders` (same pattern as `dispatch-outbox`): T-2 days before `respond_by` for recipients with `status in (sent, viewed)`; after `respond_by` with zero quotes -> `hr_rfq_no_response`.

Phase E: go-live switches and admin readiness panel
- `/admin/feature-flags`: show `SUPPLIER_RFQ_EMAIL_ENABLED`; new `GET /api/admin/email-readiness` returning `{resend_key: bool, supplier_email_live: bool, outbox_allowlist: [...], from: ...}`.

Each phase is one PR. Phase A and B do not need a migration and can ship first.

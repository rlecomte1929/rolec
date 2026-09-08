# ReloPass — First Counsel Stamp Runbook (ES→IE, Andrea's 6 EEA rows)

**Date:** 2026-08-22 · **Owner:** Romain · **Goal:** issue ReloPass's first real counsel attestation — the 6 EU/EEA employment essentials on the Madrid→Dublin corridor — and land the "Counsel-attested" badge on the served dossier.

**Pre-flight: GREEN.** All 6 target `requirement_items` are evidence-linked (real citizensinformation.ie / revenue.ie source URLs, verified 2026-08-22). The attestation system is live in prod, dormant, `promotion_policy` defaults to `manual` (signing alone serves nothing — you promote).

**Coherence note (recommended sequencing):** the same employee dossier also renders the AIQ-1887 facts panel, which today serves broken-evidence facts with clickable fake "Source" links. **Run 1887.1 (AIQ-2127, de-approve the 110 disproved) and 1887.2 (AIQ-2128, kill the fake Source links) before you issue this stamp**, so Andrea's dossier is coherent when the counsel badge appears. The stamp itself is independent and can proceed either way — but a counsel badge next to fake sources undercuts it.

---

## Steps

**1. [Romain — 🔴 gate] Approve the 6 EEA rows** at `/admin/countries` (`review_status` pending → approved). This serves them to Andrea and makes them attestable:
- `3db4efb6…` PPS Number (EU/EEA)
- `78c86802…` A1 Certificate — Posted Workers from Spain
- `ab45d82c…` Universal Social Charge
- `c5bcb3ab…` Public Health Entitlement
- `cdf091ad…` PRSI
- `e7284e86…` Irish Income Tax

**2. [Romain, or Claude Code assist] Create the attestation request** scoped to those 6 — from `/admin/attestations`, or via API:
```
POST /api/admin/attestations
{ "country_code":"IRELAND", "purpose":"employment",
  "requirement_item_ids":[
    "3db4efb6-a5d7-52b3-be20-7d42f7a31410","78c86802-f32f-5208-944d-4b642677280a",
    "ab45d82c-524f-52ce-b831-8d16a702f671","c5bcb3ab-6634-57e0-9a88-7695e6f84522",
    "cdf091ad-1b5b-56d1-ba4d-777b0a22d6ca","e7284e86-f6a1-5c72-b6ae-3af6cdda7402"],
  "reviewer_org":"<firm>","reviewer_name":"<lawyer>","reviewer_email":"<email>",
  "reviewer_credential":"Solicitor, Ireland",
  "title":"Ireland — ES→IE EU/EEA employment essentials (counsel review)" }
```
The response returns the `review_url` (`/attest/:token`) and raw token **once** — it's unrecoverable afterward (only a SHA-256 is stored), so capture it now.

**3. [Romain] Send the link + the worklist** to the lawyer: the `/attest/:token` URL plus `ReloPass_ES-IE_Counsel_Review_Worklist_2026-08-22.md` (the 6 items map 1:1; the emergency-tax item R1 is a separate scope question, not part of this attestation).

**4. [Lawyer] Reviews and signs** — decides each of the 6 (approve / amend / reject), agrees to the disclaimer, signs. No account needed; the token is the credential.

**5. [Romain — 🔴 gate] Promote** the signed request → `attestation_status='attested'` on the approved items → the "Counsel-attested" badge renders on Andrea's dossier. (Promote only flips items the lawyer marked *approved*, and only if the signature still matches the signed checklist.)

---

## Who does what
- **Romain:** approve the 6 rows, choose the lawyer, promote (the two 🔴 gates). Only you can.
- **Claude Code:** can issue the `create_attestation` call + independently verify the result against prod, if you'd rather not click through the admin UI.
- **Cowork (me):** verify the landed stamp against prod afterward (the signature row, `attestation_status='attested'` on the 6, the served badge) — my standing verifier role.
- **Otto:** not involved (no repo/DB access; it's the research agent).

## Definition of done
The 6 EEA items show `attestation_status='attested'` with the firm's name; a `corridor_attestation_signatures` row exists bound to the content hash; Andrea's dossier renders the "Counsel-attested" badge — and, if 1887.1/1887.2 have run, the facts panel beside it no longer shows fake "Source" links. ReloPass's first corridor is counsel-verified.

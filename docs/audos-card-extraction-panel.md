# Audos card — Case Command: surface document extraction

**Paste everything below the line into one Otto thread.** Single card, no dependencies.

Every fact was verified against production on 2026-08-10. The gotchas are failures that already
cost time in the backend work — they are not hypotheticals.

---

# CARD — Case Command: surface document extraction

## Why this card exists

ReloPass can now extract structured data from an uploaded passport. As of **2026-08-10** that works
end to end in production for the first time — a passport uploaded through the product produces
13 structured fields (surname, given names, document number, date of birth, expiry, nationality,
sex, personal number, plus LLM-derived issuing authority / endorsements / MRZ-vs-body discrepancies
/ agent confidence).

**Nothing in the product shows any of it.** The data lands in the backend and is invisible to the
HR user. Your job is to close that gap in **Case Command**.

This matters for the wedge: the pitch is "know what you don't know before week seven". A case that
silently already knows the employee's passport expires before the assignment ends — and doesn't say
so — is the product failing at its own premise.

## What to build

A **Documents** panel in Case Command, per case, that answers three questions at a glance:

1. **What has this employee actually uploaded?** (type + filename + when)
2. **Did the system understand it?** (was anything extracted, and how confidently)
3. **What needs a human?** (low confidence, or nothing extracted at all)

Design for the **empty and partial cases first** — see gotcha 2. A panel that only looks right when
extraction succeeds will look broken most of the time.

## The API

```
POST https://api.relopass.com/api/auth/login
  {"identifier": "<email>", "password": "<password>"}   ->  { "token": "..." }

GET  https://api.relopass.com/api/hr/cases/{case_id}/documents
  Authorization: Bearer <token>
```

Response:

```json
{ "documents": [ {
    "document_id": "…", "document_type_code": "PASSPORT_TD3",
    "document_type_label": "…|null", "filename": "passport_probe_aiq1780.png",
    "uploaded_at": "…", "confidence_mean": 0.93, "confidence_min": 0.50,
    "extracted_field_count": 22, "document_uri": "…|null", "page_count": null
} ] }
```

Related endpoints on the same case, worth showing beside it if it fits naturally:
`/{case_id}/overview`, `/{case_id}/steps`, `/{case_id}/contradictions/summary`.

**Credentials (seeded demo tenant, safe to use):**
`hr@testingapril.com` / `HrPass!1` — HR, company `c0000000-…-0001`.

**Live case with real extracted data, created 2026-08-10:**
`08b7280b-491d-4d50-ae8b-325cb29aa3f1` — 1 document, `PASSPORT_TD3`, 22 field rows.
Verified this HR user can read it.

## Gotchas — each one already bit someone

1. **`extracted_field_count` over-counts.** It aggregates every extraction run for a document, and
   re-processing appends rather than replaces. The test case reads **22 for a 13-field document**
   (it was processed twice). **Do not label it "fields extracted".** Either present it as a yes/no
   signal ("data extracted ✓") or say "22 field records across all runs". Getting this wrong puts a
   number in front of a customer that is simply false.

2. **Most documents extract nothing, and that is expected right now.** Only passports currently
   extract; every other type (marriage certificate, tax certificate, diploma, employment contract)
   returns `extracted_field_count: 0` or `null`, because its OCR engine is not yet enabled. Show
   "not yet processed", never an error state. This will be the majority case.

3. **`confidence_mean` understates quality.** Passport MRZ fields come back at confidence `1.000`
   (deterministic); LLM-derived fields sit at `0.50–0.95`. Averaging them drags the number down and
   makes a perfect read look mediocre. Prefer `confidence_min` for a "needs review" flag, and
   consider not surfacing a single blended score at all.

4. **Extraction is asynchronous.** Upload returns HTTP 200 immediately; fields appear ~5–15s later.
   A panel that reads once, right after upload, will show zero. Poll or offer refresh.

5. **404 does not mean "no such case".** The endpoint returns 404 (not 403) on tenant mismatch, by
   design, so an attacker cannot probe which case IDs exist. On a 404, suspect the wrong tenant
   before concluding the case is missing.

6. **Log in once.** `/api/auth/login` is rate-limited to 5/minute. Reuse the token; no retry loops.

7. **`document_type_label` and `page_count` can be null.** Fall back to `document_type_code`.

## Definition of done

- Panel renders for the live case above and shows the passport with its real filename and type.
- Renders correctly for a case with **no** documents, and for a document with **zero** extracted
  fields — screenshot both.
- Field-count presentation is honest per gotcha 1 — state in your report which wording you chose.
- A short note on what an HR user still **cannot** answer from this panel. That gap list is as
  valuable as the panel itself.

## Rules

```
- You cannot see our repo or our database. Do not state a fact about either.
- Label every claim [VERIFIED] (you observed it) or [CLAIM] (you inferred it).
- Read-only against api.relopass.com: GET only, plus the one login POST. Upload nothing,
  approve nothing, delete nothing.
- Use only the hr@testingapril.com tenant. Do not touch other tenants or campaign insead-2026.
- A blocked path is a FINDING, not something to route around. "NONE" is a valid answer.
- A FAIL is not final until you capture the exact failing request (URL + status + body),
  or you say INCONCLUSIVE. An empty panel is not a FAIL until you name the failing request.
- Stop before the budget cap. Never die mid-action.
```

## Context you may be told and should not act on

The backend work behind this is finished and merged — you are **not** fixing extraction, only
surfacing it. If the panel shows nothing for the live case above, that is a **finding to report**,
not a signal to go looking for backend fixes you cannot make.

# Audos card — walk the document-upload journey (WRITE access)

**Paste everything below the line into its own Otto thread.**

Companion to `docs/audos-card-extraction-panel.md`. That one is read-only and builds a surface;
this one is browser QA **with write access** to the seeded demo tenant. Run this one **first** —
what it finds should shape the panel.

**Why write access is justified here:** the upload journey has never been walked by a human. The
backend was proven end to end on 2026-08-10 by calling the API directly, which deliberately skips
the part most likely to be broken — whether a real employee can *find* the upload at all.

---

# CARD — Walk the document-upload journey end to end

## Why this card exists

On 2026-08-10 ReloPass extracted structured data from a passport in production for the first time.
That was proven by **calling the API directly** — no browser, no UI. So we know the pipeline works
and we know **nothing** about whether a real person can reach it.

Two specific unknowns, both of which the API test could not touch:

1. **Is the upload discoverable?** There is a known-dead sibling route cluster
   (`/hr/immigration/*`) with zero inbound links from the sidebar — reachable only by typing the
   URL. It has therefore received **zero uploads ever**. The employee document path may be in a
   similar state. If you cannot find the upload without being told where it is, **that is the
   headline finding**, not a failure to complete the card.
2. **Does the product acknowledge extraction?** After a successful upload the backend produces
   ~13 structured fields. We believe the UI shows none of it. Confirm or refute.

## The journey to walk

Log in as the **employee** and behave like someone who has been told "upload your passport":

```
https://relopass.com   (the live product)
employee@testingapril.com / EmpPass!1
```

1. **Land, and look.** Before navigating anywhere deliberately, record what an employee sees on
   arrival. Is there any prompt to upload a document? Screenshot the landing state.
2. **Try to find the upload the way a user would** — sidebar, roadmap/plan tasks, any "upload"
   call-to-action on a task card. **Count the clicks** and note every dead end.
3. **If and only if you cannot find it**, use the direct route as a fallback so the rest of the card
   can proceed — and record that you needed it:
   `https://relopass.com/employee/case/08b7280b-491d-4d50-ae8b-325cb29aa3f1/documents`
4. **Upload the file** (see "What to upload").
5. **Observe for 60 seconds.** Extraction is asynchronous — the upload returns immediately and
   fields land ~5–15s later. Does the page change at all? Does anything indicate the document was
   read, understood, or accepted? Refresh and look again.
6. **Look for the extracted data anywhere in the product** — the case page, a documents list, a
   task status flipping to complete. Report where you looked, not only what you found.

## What to upload

**The filename must contain the word `passport`** (e.g. `passport_probe.png`). Document routing is
driven by the *filename*, not by any type selector you pick in the UI — a file named `scan001.png`
is classified as nothing and extraction never runs. This is a real backend quirk, not a hint.

Use a **passport biographical-page image** (PNG or JPEG, under 20 MB). Romain will supply one; if
none is supplied, upload any clearly non-genuine passport-style image and note that extraction may
not fire. Accepted types: PDF, PNG, JPEG, WebP, TIFF.

## A defect we already predict — please confirm it

The frontend calls `DELETE /api/cases/{caseId}/documents/{documentId}`. **The backend defines only
POST and GET on that path** — there is no delete handler. So if the UI offers a way to remove an
uploaded document, it should fail.

Find out whether a delete control is exposed, and if so, click it and capture the exact failing
request (URL + status + response body). If no delete control exists, say so — that is equally
useful. **This is the one place you are permitted to attempt a destructive action**, and only on a
document you uploaded yourself in this run.

## Write access — scope

**Permitted:**
- Log in as `employee@testingapril.com` (tenant `testingapril`, company `c0000000-…-0001`).
- Upload documents to case `08b7280b-491d-4d50-ae8b-325cb29aa3f1`.
- Attempt to delete **only** a document you uploaded during this run (see above).

**Not permitted — a breach here is stop-everything:**
- Any other tenant, case, or user. Never `insead-2026`.
- HR or admin actions of any kind: approving suppliers, dispatching outreach, sending email,
  changing case status, editing policy.
- Applying migrations, creating tables, deleting anything you did not create in this run.
- Stripe: test mode only, on-screen test card only. A real payment is stop-everything.

**Keep it to 2 uploads maximum.** This tenant is *not* covered by the automated test-data purge, so
everything you create persists. Name files identifiably (`passport_audos_<date>.png`) so we can find
them later.

## Gotchas — each already cost time

1. **The 200 means nothing.** Upload returns HTTP 200 as soon as the file is stored. Everything
   downstream is detached and fail-soft, so a green toast is not evidence of extraction. Only what
   the UI shows afterwards counts for this card.
2. **Extraction is stochastic on synthetic images.** The vision model sometimes rejects a test
   passport as a "specimen" and extracts nothing — the same image succeeded on one run and failed on
   the next. If nothing extracts, **retry once** before reporting it as broken, and report both
   attempts.
3. **Only passports extract today.** Every other document type returns zero fields because its OCR
   engine is not yet enabled. A marriage certificate showing nothing is expected, not a bug.
4. **Log in once.** The login endpoint is rate-limited to 5/minute. No retry loops.
5. **Decline the analytics consent banner** — it overlays the page, blocks clicks, and reappears
   after navigation.
6. **Type by keyboard.** Setting a field programmatically does not fire the React handler.

## Definition of done

- **A click-path map** from landing to upload, with the click count and every dead end — or a clear
  statement that you could not find it unaided and had to use the direct URL.
- Screenshots: landing state, the upload control, mid-upload, and the page 60s after.
- A plain answer to: **after uploading a passport, does the product tell the employee anything about
  what was extracted?** Yes/no, with the evidence.
- The delete finding (control exists or not; if it exists, the exact failing request).
- A short list of what an employee *cannot* tell from this journey. That gap list is the most
  valuable output of this card.

## Rules

```
- You cannot see our repo or our database. Do not state a fact about either.
- Label every claim [VERIFIED] (you observed it) or [CLAIM] (you inferred it).
- Write access is scoped to the list above. Anything outside it is stop-everything.
- Click custom controls by coordinate, never by ref. Ref-clicks silently no-op on several
  of our controls.
- PageDown for inner scroll containers — they ignore the mouse wheel.
- One fixture per browser session. Confirm the top-right account label before acting.
- A blocked path is a FINDING, not something to route around. "NONE" is a valid answer.
- A FAIL is not final until you capture the exact failing request (URL + status + body),
  or you say INCONCLUSIVE. An empty panel is not a FAIL until you name the failing request.
- Stop before the budget cap. Never die mid-action.
```

## Context you may be told and should not act on

The backend extraction work is finished and merged. You are **not** fixing it. If extraction does
not fire, or the UI shows nothing, that is a **finding to report** — not a signal to go looking for
backend fixes you cannot make.

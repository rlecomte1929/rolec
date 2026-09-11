# AD-P5 · Singapore driving-licence conversion guide (FR->SG)

**batch_id:** `sg-driving-licence-2026-09-10`
**corridor:** FR-SG (Paris -> Singapore) · **persona:** Adrien, French national on Employment Pass
**artifact:** `sg-driving-licence-2026-09-10.bundle.json` · **resources:** 4 · **events:** 2
**sha256:** `637c0ad1aeb21153e309941236bbe2a6bf12a6385eb558a6a944cf9f3b9b0465`

## Status
All resources and events: `status: draft`. Candidate-only, awaiting verification.

## What the guide answers
- **Can Adrien drive on his French licence, and for how long?** Yes initially, but a resident staying beyond **12 months** must convert (Traffic Police Foreign Licence pre-assessment), and anyone who **drives for work** must convert within **6 months** of their work pass being issued (police.gov.sg).
- **Is France exempt from the Basic Theory Test (BTT)?** **No exemption is published.** The Traffic Police require passing the BTT to convert, and their page does not identify any countries as exempt. A French licence holder must pass the BTT.
- **Deadline to convert:** 6 months (if driving for work) / before exceeding 12 months' residence (general).
- **Where to apply:** Traffic Police online Foreign Licence Pre-assessment -> pass BTT -> book conversion appointment (SPF e-services).

## Sources (official only)
- **police.gov.sg** - Singapore Driving Licence (Traffic Police); conversion e-service; documents checklist (PDF)
- **form.gov.sg** - Traffic Police Foreign Licence Conversion pre-assessment (official Singapore Government form)

## Source access issues (honest log)
- `police.gov.sg` is a script-rendered site: the standard scraper returned only page chrome. The substantive rules (BTT requirement, 6-month work-driving deadline, "no countries exempt" from the BTT) were extracted via an alternate fetch of the same official URL. The BTT-exemption resource is flagged in-body to re-confirm against the live page before operational use.
- The Traffic Police documents-checklist PDF could not be fully scraped; the document list is stated as indicative (from the official checklist) and flagged for verification.
- **No BTT-exemption status, fee, or deadline was invented.** The France-not-exempt statement rests on the Traffic Police page not publishing any exemption list.

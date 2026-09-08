# UAE destination facts (2026-08-31)

UAE opened as a destination (coverage-master rank 8, Dubai hub), greenfield (0 prior rows). Sourced to
u.ae, tax.gov.ae, icp.gov.ae, gdrfad.gov.ae by a Claude Code research subagent. All facts non-EEA →
THIRD_COUNTRY (UAE is non-EEA). Scope guard exit 0.

## What landed (16 facts → 9 requirement_items, all pending/representative)
Personal income tax (none) · Corporate tax not on salary · Emirates ID (mandatory + carry duties) ·
Residence permit (linked to EID; 2-year validity) · Medical fitness test + communicable-disease screen ·
Health insurance in Dubai (employer-provided; 1 Jan 2025 prerequisite for residency) · Work permit (MoHRE,
employer-held, approval allows entry) · Employment contract registration (14 days) · Work only for your
sponsor · Overstay fines.

## Code this batch required
- `requirements_country_key.py`: `"AE":"UNITED ARAB EMIRATES"` (+ `test_uae_is_covered`).
- `backend/imports/otto/parsers.py` `_OFFICIAL_SUFFIXES`: `gov.ae` + `u.ae` (7th too-narrow-allowlist
  instance — `.gov.ae` ≠ bare `.gov`).

## Referee caveat (honest)
u.ae is a JS SPA; verify_ledger's fetcher gets intro-only, so only 5/16 quotes re-confirmed in-tool (1
dropped to worklist as a real mismatch). The subagent confirmed the u.ae quotes via WebFetch (full body).
15 importable → 9 requirement_items. **Re-confirm the u.ae-sourced quotes (via WebFetch) before approval.**

## Rejects / honest gaps (subagent)
Entry-permit 2-month validity (old u.ae URLs 404 after site restructure) and the 9% corporate-tax rate
(no clean verbatim) were NOT asserted — captured the entailment without the number.

Gate remaining (human): approve at /admin/countries (UNITED ARAB EMIRATES); serving needs the catalog +
allowlist merged (PR #2138).

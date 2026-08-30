# Provider validation & coverage — architecture plan

**Status:** design reference (not yet built) · **Date:** 2026-08-30 · **Author handoff:** written to be
picked up cold in a fresh session.

## 1. What this is

A long-run plan for how service providers (movers, housing agencies, schools, banks, legal/tax
advisors, and future categories) get **sourced → validated → served** to employees, and how the
platform expands to **new locations** and **new services** on demand.

The north star: an employee gets a bespoke relocation roadmap whose every recommended provider has
been validated by the right authority — and when a provider is missing for their service+location,
the gap becomes a request that fills itself rather than a dead end.

**Two validators, by design (this is the founder's stated model):**
- **Admin validates the provider platform-wide** — "is this a legitimate, accredited, contactable
  provider for this service in this location?"
- **HR validates the provider for their company** — "do we offer this provider to our employees?"

An employee sees a provider only when **both** have said yes.

## 2. Current state — what already exists (grounded, with paths)

The two-gate model is **half-built**. Do not greenfield; extend these.

### The two gates already work
- **Admin / platform gate:** `public.supplier_service_capabilities.platform_vetting_status`
  ∈ `pending | approved | rejected | suspended`. The recommendation engine surfaces **only
  `approved`** — `backend/app/services/supplier_registry.py::search_by_service_destination`
  filters `Supplier.status='active'` AND `platform_vetting_status='approved'` AND service+country.
- **HR / company gate:** `backend/app/services/employee_recommendations_filter.py` keeps only the
  master items HR selected for the company (`public.company_vendor_selections`). It already emits
  the signals this plan builds on: **`hr_pending`** (HR curated nothing) and
  **`hr_destination_gap`** (HR has picks, but none for THIS destination).
- Wired together in `backend/app/recommendations/engine.py::recommend(...)` — when `company_id` is
  supplied, the employee sees platform-approved ∩ HR-curated; otherwise (admin/debug) the filter is
  skipped.

### The provider tables (five, overlapping — see `docs/supplier-systems-state.md`)
- `public.suppliers` (+ `supplier_service_capabilities`) — **authoritative** for recommendations +
  RFQ. This is the target of validation. `suppliers.verified` (bool) gates RFQ dispatch
  (`supplier_link_dispatch.py`); `contact_email` is the only RFQ address source.
- `service_catalog_items` (+ `company_vendor_selections`) — the HR-selects-vendors surface
  (`/hr/service-providers?tab=vendor`).
- `vendors_legacy` — display-only, write-revoked.
- `vendor_candidates` — the sourcing staging table (has no product reader; promoted via
  `backend/imports/suppliers/executor.py::promote()` → `suppliers` at `platform_vetting_status='pending'`).

### Coverage tracking + sourcing already partly exist
- `public.corridor_coverage_targets` — target vs `current_verified_count` per corridor (the
  flywheel migration; see `backend/app/services/registry_sources.py`, `vendor_harvester.py`).
- Sourcing pipeline: **Otto research → Claude grounds → land candidates → admin vets**, documented
  in `docs/otto/vendor-sourcing-challenge-brief-2026-08-30.md` and the requirement-facts twin
  `docs/otto/requirement-facts-roundtrip-2026-08-30.md`. The vendor CSV reader is
  `backend/imports/suppliers/parsers.py` (`vendor_harvester.validate()` = tier + GDPR-email gate).
- The six **live** categories: `supplier_service_categories.is_live=true` for `legal_admin`,
  `tax_finance`, `movers`, `housing_agencies`, `schools`, `banks`
  (`supabase/migrations/20260805214336_brain3c_supplier_qualification.sql`).
- Each live category has a recommendation plugin: `backend/app/recommendations/registry.py`.

### What is MISSING (the subject of this plan)
1. **No coverage-request loop.** Gaps (`hr_destination_gap`, no approved provider for a service ×
   location) are detected but nothing turns them into a prioritised sourcing request.
2. **Accreditation isn't systematically verified.** Providers land with an Otto-*claimed* FIDI/IAM
   membership (unverified); the admin validator has no evidence pane and no auto directory-check.
3. **No first-class "onboard a new location / new service" path.** Adding EC or a new category is
   ad-hoc (the `_ISO_TO_CATALOG_NAME` / `catalog_destination_allowlist` gates bite silently).

## 3. Target architecture

### 3.1 One provider lifecycle (a status spine)
```
candidate            (vendor_candidates — Otto-sourced, contactability + accreditation NOT yet checked)
  → platform_pending (promoted to suppliers; supplier_service_capabilities.platform_vetting_status='pending')
  → [ADMIN VALIDATES] evidence shown: grounded contact inbox + accreditation directory entry
  → platform_approved | platform_rejected | suspended
  → [HR VALIDATES]    company_vendor_selections — HR offers it to their people
  → company_selected
  → employee sees it  (platform_approved ∩ company_selected, for the employee's service × location)
```
Nothing reaches an employee without both validations. `suppliers.verified` (RFQ gate) is set at, or
after, admin approval once the contact inbox is confirmed.

### 3.2 The coverage-request loop (the missing keystone)
A `provider_coverage_request` concept — *"service S is needed at location L"* — dedup'd by
`(service_category, country, city)`:
- **Raised by:** a real case hitting `hr_destination_gap` / no-approved-provider; an HR ask; or an
  admin. Each raise increments a **demand counter** so sourcing + validation are prioritised by
  real need, not guesswork.
- **Fulfilled by:** the existing Otto round-trip — *request → Otto sources providers for S×L →
  Claude grounds contactability + verifies accreditation against the directory → land as
  `vendor_candidates` → admin validates (evidence pane) → HR curates → requester notified.*
- **Backed by:** extend `corridor_coverage_targets` (or a sibling table) into the demand ledger:
  `requested_demand`, `target_count`, `current_approved_count` per (service × location).

This is what turns "no movers in Lisbon" from a dead end into a self-filling request.

### 3.3 Extensibility — new locations and new services are the SAME request
| Request | Onboarding prerequisite (the gates that bite) | Then |
|---|---|---|
| **New location** (existing service, new city/corridor) | add to `_ISO_TO_CATALOG_NAME` (`backend/app/services/requirements_country_key.py`) + `catalog_destination_allowlist`; register the corridor in `KNOWN_CORRIDORS` (`hr_vendors.py`) | source → validate → serve |
| **New service** (not-yet-live category) | flip `supplier_service_categories.is_live=true`; **register a recommendation plugin** in `backend/app/recommendations/registry.py`; define its accreditation directory (if any) | source → validate → serve |

Both flow through the identical sourcing + two-gate validation pipeline — only the prerequisite differs.

### 3.4 Make validation scale (validation is the bottleneck)
- **Prioritise by demand** — validate the (service × location) combos real cases request first; the
  coverage-request ledger is the signal.
- **Systematise accreditation** — auto-check the per-category registry (FIDI/IAM for movers, Law
  Society / bar for legal, etc.) so admin validation is a *confirmation with the directory entry on
  screen*, not manual research. This is the `source_url` / directory-entry gap flagged on the
  Madrid→Dublin movers batch — a provider isn't admin-approvable until its directory entry resolves.
- **Batch vetting** — admin approves a whole corridor's candidates at once, reusing the Otto batch
  structure (`docs/imports/<batch>/`).

## 4. Suggested build sequence (each phase is a session's worth)

1. **Coverage-request ledger + gap capture.** Table + write path from the existing gap signals
   (`hr_destination_gap`, empty approved set). Read: an admin/HR view of "what's requested, ranked
   by demand." *Keystone — build first.*
2. **Admin validation surface with an evidence pane.** Show, per pending provider: grounded contact
   inbox, source/accreditation directory entry, corridor. Approve/reject writes
   `platform_vetting_status`. (Extends the existing `/admin/vetting-queue`.)
3. **Accreditation auto-verification.** Per-category directory checkers (movers = FIDI/IAM) that
   resolve a provider's directory entry and attach it as evidence; block approval without one.
4. **Request → Otto sourcing trigger.** A coverage request kicks the round-trip for that S×L; the
   result lands as candidates against the request; requester notified on approval.
5. **New-service / new-location onboarding flows.** Wrap the prerequisite gates (§3.3) so onboarding
   is one guided action, not silent allowlist edits.
6. **Demand-driven prioritisation + batch vetting.** Rank the validation queue by demand; batch-approve.

## 5. Open decisions (resolve early in the build)
- **Consolidate the five provider tables** or keep `suppliers` authoritative and adapt around it?
  (`docs/supplier-systems-state.md` calls consolidation a real follow-up.) Recommend: keep
  `suppliers` authoritative; do not add a sixth table.
- **Where does `verified` (RFQ gate) get set** — at admin approval, or a separate step? Recommend:
  at approval, once the contact inbox is confirmed live.
- **Company-agnostic vs company-scoped requests** — is a coverage request global (any company
  benefits) or per-company? Recommend: global sourcing, per-company HR curation (the demand counter
  aggregates across companies).

## 6. Session context (what exists as of 2026-08-30, for the fresh session)
Built/verified this session and relevant to this plan:
- **6 Madrid→Dublin movers landed** in `suppliers` (ids `mov-*`), each with an approved
  `movers`/`IE` capability, grounded contact inboxes, `verified=false` (accreditation unverified —
  RFQ gated). They appear in the movers recommendation for Dublin. This is the first real exercise
  of the admin-approved gate.
- **Vendor email gate widened** (PR #2097, merged) — `vendor_harvester.validate()` now accepts
  `sales@`/`enquiries@`/`hq@` etc. (root cause of "115/122 uncontactable").
- **Nationality-aware roadmap** (PR #2098, merged) — free movers no longer see the visa track;
  mirrors `requirements_builder`'s nationality gate. A template for making other surfaces
  audience-aware.
- **Otto→verify→land round-trip proven** for both requirement facts and the movers batch — the
  sourcing engine this plan's request loop feeds into.
- Related memory: `project_otto_relopass_knowledge_pipeline`, `reference_audos_egress_is_gcs_export_only`,
  `reference_hr_vendor_curation_surface_exists`, `reference_case_vendor_registry_is_vendors_legacy`.

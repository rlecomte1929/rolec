# Vendor enrichment — 2026-09-09 (first proving batch)

Turns the thin identity records the harvest produces (name / website / register-id) into records
carrying the fields the product actually reads. Generalizes the **proven 2026-08-31 contact loop**
(148 firms → +83 contacts, keyed on `supplier_id`, SHA-verified, fill-empty) to the full
product-consumed field set. Applier: [`scripts/enrich_suppliers.py`](../../../scripts/enrich_suppliers.py).

## What is enriched (product-consumed fields ONLY)

`suppliers`: `contact_email`, `contact_phone`, `description`, `languages_supported`.
`supplier_service_capabilities` (keyed on `supplier_id` + `service_category`): `specialization_tags`,
`min_budget`, `max_budget`, `city_name`.

The ~17 columns no product surface reads (VAT, payment-terms, SLA, reg-number, `named_single_contact`,
`based_in_country`, …) are deliberately **not** touched — filling them changes nothing user-visible
until a reader is built. Full rationale + per-field consuming surface: the approved plan.

## The loop (per capital × category)

1. **Export** the target list keyed on `supplier_id` (never domain/name):
   `SELECT s.id, s.name, s.website FROM suppliers s JOIN supplier_service_capabilities ssc … WHERE
   s.source='directory_import' AND s.website<>'' AND ssc.service_category=:cat AND ssc.country_code=:cc
   AND (contact_email empty OR description empty OR specialization_tags empty)` → `target_<slice>.csv`.
2. **Dispatch** the enrichment brief to Otto via the automation session (chunk ~15–26 firms). Otto
   returns NDJSON (per firm: contact/description/languages/tags/city + per-field `*_source_url` +
   `confidence` + `status` + `notes`) + a manifest (`sha256_ndjson`, `record_count`) on public GCS.
3. **Gate** (offline): `python gate.py` re-hashes `src/<slice>.ndjson` vs `manifest_<slice>.json`,
   reconciles the count, and asserts every key ∈ `target_<slice>.csv`.
4. **Integrate** (fill-empty, dry-run default):
   ```bash
   python scripts/enrich_suppliers.py docs/imports/vendor-enrichment-2026-09-09/src/<slice>.ndjson \
       --category <cat> --manifest <manifest> --target-keys <target.csv>          # preview
   python scripts/enrich_suppliers.py … --apply                                    # write
   ```
   Fill-empty is decided in Python (read-then-decide), so a non-empty (curated/approved) value is
   **never** overwritten. `--apply` measures the append-only tripwire (approved-capability count+md5
   over `id|platform_vetting_status|service_category`) before/after and **rolls back if it moved**.

## Sub-batches

### XX-DE schools (Berlin + Frankfurt) — `vendor-enrichment-schools-de-2026-09-09` (LANDED 2026-09-09)
- Target: the **13** Berlin+Frankfurt international schools landed today (`target_xx-de-schools.csv`),
  all 0% enriched before this run. Source (GCS): `1788967537614_fc9jlxue.ndjson` (+ manifest
  `1788967548147_b55o0wy8.json`), sha256 `1971ed7e…` (independently re-computed = manifest).
- Otto status: **8 found / 4 partial / 1 unreachable.** All 13 keys echoed verbatim (gate: keys ⊆
  target, sha + count OK). Independently re-verified **every one of the 11 returned emails appears on
  its cited page** (curl) — including 4 whose email is on a sibling domain (ASB Erasmus ×2,
  Berlin Bilingual, JFK→`jfksberlin.org`): all confirmed on-page, so the multi-domain recovery is
  honest, not fabricated. IBMS email confirmed on its `/contact` sub-page.
- Landed: **70 fields filled across 12 schools** (fill-empty, dry-run-reviewed) — 11 contact_email,
  11 contact_phone, 12 description, 12 languages, 12 specialization_tags, 12 city_name (now precise:
  Bad Homburg, Bad Vilbel, Frankfurt am Main, Berlin). **0 overwrites.**
- **Honest skips:** SIS Swiss Frankfurt = `unreachable` (subdomain ECONNREFUSED) → whole row skipped,
  left empty (not fabricated); accadis = email null (contact-form only, phone/rest filled); Berlin
  Cosmopolitan = phone null (`/contact` 500'd, email/rest filled).
- **Append-only tripwire held:** approved-capability count+md5 **130 → 130** `1c4c3899…` unchanged;
  pending unchanged at 1019 (enrichment adds no rows). First real `enrich_suppliers.py --apply`,
  proven end-to-end.

## Honesty (Otto self-applies; the applier re-checks)

No fabrication — a field not on the firm's own site is null. The applier drops any field with no
`*_source_url` (for contact/description), `confidence=low`, or a `not_found`/`unreachable` row status,
and has an email backstop (skips `security@`/`fraud@`/`presse@`/`dpo@`/`privacy@` local-parts).
Nothing here is served — enrichment fills fields on `pending`/`approved` suppliers; visibility is still
the human `platform_vetting_status='approved'` gate at `/admin/vetting-queue`.

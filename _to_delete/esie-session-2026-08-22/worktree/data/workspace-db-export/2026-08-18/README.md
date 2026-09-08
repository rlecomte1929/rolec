# ReloPass WorkspaceDB snapshot — 2026-08-18

A complete, versioned copy of the ReloPass Audos WorkspaceDB, exported
2026-08-18 and imported here so the canonical data lives in the
platform of record rather than only in the hosted Audos database.

| | |
|---|---|
| Export name | ReloPass WorkspaceDB full export |
| Workspace ID | `d0c29613-9cb5-4652-9c6a-494eeed352e5` |
| Exported at | `2026-08-18T17:47:03.642586+00:00` |
| Uploaded at | `2026-08-18T17:52:31.999130+00:00` |
| Tables | **75** (61 non-empty, 14 empty) |
| Rows | **12,207** (12,196 committed, 11 in git-ignored `_pii/`) |
| Bytes | **58,205,902** (~58.2 MB) |
| Files | 74 committed + `MANIFEST.json`; 2 in `_pii/` |
| Row-count drift | none - workspace_db_list_tables counts were identical before and after the export |

`MANIFEST.json` is the source of truth for this directory: it indexes every
file with its URL, byte size, sha256, and row count. Everything else here was
verified against it.

## PII — two tables are deliberately NOT committed

`persons.json` (6 rows) and
`person_identities.json` (5 rows)
contain personal data. They live in `_pii/`, which is git-ignored.

**This is a deliberate choice, not an oversight.** Committing them would have
been permanent: git retains history, so deleting them in a later commit would
not undo it. Keeping them out means

- the option of ever making this repo public stays open, and
- a GDPR erasure or rectification request against the source tables does not
  have to chase a frozen copy that git would keep forever.

They stay fully reproducible — `MANIFEST.json` is committed and carries both
URLs and sha256s:

```bash
cd data/workspace-db-export/2026-08-18
mkdir -p _pii
python3 - <<'EOF'
import json, urllib.request, pathlib
m = json.load(open("MANIFEST.json"))
for t in m["tables"]:
    if t["table"] in ("persons", "person_identities"):
        for f in t["files"]:
            urllib.request.urlretrieve(f["url"], pathlib.Path("_pii") / f["file"])
            print("fetched", f["file"])
EOF
python3 validate.py        # now verifies all 75 tables
```

## File shape

Every per-table file has the shape:

```json
{ "table": "countries", "sqlName": "app_countries",
  "exported_at": "…", "rowCount": 8, "rows": [ … ] }
```

- `table` is the friendly name; `sqlName` is the physical Postgres name.
- **`app_corridors` (`app_app_corridors`) and `app_vendor_providers`
  (`app_app_vendor_providers`) are distinct tables from `corridors` and
  `vendor_providers`.** The doubled `app_` prefix is not a typo — do not
  conflate the pairs.
- `linked_references` is split across two files because of upload size limits.
  The parts add `part`, `totalParts`, and `partRowCount`; each part's
  `rowCount` is the whole-table total (6,421), and the parts concatenated **in
  order** equal the full table.
- Timestamps are ISO-8601 UTC strings. `id` is an integer for most tables and
  text for a few (`notion_tasks`, `kg_corridors`, `kg_employee_types`,
  `kg_corridor_requirements`, `kg_case_verification_reports`);
  `employee_types` has no `id` column at all.

## Integrity — re-verify offline at any time

```bash
python3 data/workspace-db-export/2026-08-18/validate.py
```

`validate.py` is stdlib-only (json, hashlib, pathlib), needs no network access,
and for every manifest entry it recomputes the sha256 of the bytes on disk,
compares the byte size, parses the JSON, checks the row count (per-part for the
split table, and that the parts sum to the table total), and checks that ids are
unique within each table that has an `id`. It prints a line per table and exits
non-zero if anything fails.

The two PII tables report `SKIP` when `_pii/` is absent, and are verified
normally when it is present. That skip is narrow by design:

- it applies **only** to those two tables;
- a PII file that IS on disk but tampered with still **FAILS**;
- any other missing file is still a hard **FAIL**;
- the totals must still reconcile — verified rows plus skipped rows must equal
  the manifest total, so a file cannot go missing unnoticed.

## Data fidelity — do not edit these files

The row data was produced mechanically from raw DB reads and is committed
**byte-identical** to what was downloaded. Never edit, reformat, re-key,
pretty-print, or "fix" row contents: any of those breaks the sha256 and
destroys the guarantee this directory exists to provide. Re-export from the
source database instead.

Two observations that are **properties of the source data**, not import damage
(the committed bytes match the manifest sha256 exactly):

- 3 of the 6,421 `linked_references` rows (ids 2799, 3506, 6411) contain
  mis-decoded UTF-8 in their scraped `content` field — e.g. `Ã¨` for `è`,
  `zurÃ¼cksetzen` for `zurücksetzen`. These pages were mangled at scrape time,
  upstream of the export. Preserved as-is.
- All other files decode as clean UTF-8 and read as normal prose.

## Empty tables (14)

These tables had zero rows at export time and are committed as `"rows": []`.
They are part of the snapshot — their emptiness is data. **Never fabricate or
backfill rows.**

- `app_vendor_providers`
- `attestations`
- `audit_events`
- `case_addons`
- `case_evidence`
- `corridor_deadline_events`
- `engagements`
- `notifications`
- `outreach_contacts`
- `relopass_vendors`
- `requirement_decay_queue`
- `research_passes`
- `sign_offs`
- `vendor_sourcing_requests`

`attestations` in particular is the authoritative lawyer-verdict table. It was
empty at export time and must remain an empty rows array.

## Size

This directory adds ~56 MB, of which `linked_references.part1of2.json` alone is
42 MB. That is under GitHub's 100 MB file limit and clones fine, but it is a
permanent cost to every clone. If snapshots start recurring rather than being a
one-off, Git LFS or an out-of-repo archive with only the manifest committed
would age better.

## Tables

| Table | sqlName | Rows | Files |
|---|---|---:|---|
| `app_corridors` | `app_app_corridors` | 1 | `app_corridors.json` |
| `app_vendor_providers` | `app_app_vendor_providers` | 0 _(empty)_ | `app_vendor_providers.json` |
| `approvals` | `app_approvals` | 17 | `approvals.json` |
| `attestation_claims` | `app_attestation_claims` | 23 | `attestation_claims.json` |
| `attestations` | `app_attestations` | 0 _(empty)_ | `attestations.json` |
| `audit_events` | `app_audit_events` | 0 _(empty)_ | `audit_events.json` |
| `authorities` | `app_authorities` | 8 | `authorities.json` |
| `case_access` | `app_case_access` | 2 | `case_access.json` |
| `case_addons` | `app_case_addons` | 0 _(empty)_ | `case_addons.json` |
| `case_document_uploads` | `app_case_document_uploads` | 6 | `case_document_uploads.json` |
| `case_evidence` | `app_case_evidence` | 0 _(empty)_ | `case_evidence.json` |
| `case_facts` | `app_case_facts` | 24 | `case_facts.json` |
| `case_obligations` | `app_case_obligations` | 10 | `case_obligations.json` |
| `case_timeline_events` | `app_case_timeline_events` | 7 | `case_timeline_events.json` |
| `case_verification_reports` | `app_case_verification_reports` | 1 | `case_verification_reports.json` |
| `cases` | `app_cases` | 7 | `cases.json` |
| `city_capabilities` | `app_city_capabilities` | 55 | `city_capabilities.json` |
| `competitive_reports` | `app_competitive_reports` | 7 | `competitive_reports.json` |
| `compliance_checklist_items` | `app_compliance_checklist_items` | 15 | `compliance_checklist_items.json` |
| `confidence_dimensions` | `app_confidence_dimensions` | 6 | `confidence_dimensions.json` |
| `coordinators` | `app_coordinators` | 6 | `coordinators.json` |
| `corridor_candidate_sets` | `app_corridor_candidate_sets` | 3 | `corridor_candidate_sets.json` |
| `corridor_deadline_events` | `app_corridor_deadline_events` | 0 _(empty)_ | `corridor_deadline_events.json` |
| `corridor_requirement_candidates` | `app_corridor_requirement_candidates` | 35 | `corridor_requirement_candidates.json` |
| `corridor_requirements` | `app_corridor_requirements` | 63 | `corridor_requirements.json` |
| `corridor_research_findings` | `app_corridor_research_findings` | 9 | `corridor_research_findings.json` |
| `corridors` | `app_corridors` | 3 | `corridors.json` |
| `countries` | `app_countries` | 8 | `countries.json` |
| `decisions` | `app_decisions` | 1 | `decisions.json` |
| `document_types` | `app_document_types` | 14 | `document_types.json` |
| `employee_types` | `app_employee_types` | 4 | `employee_types.json` |
| `engagements` | `app_engagements` | 0 _(empty)_ | `engagements.json` |
| `events_calendar` | `app_events_calendar` | 514 | `events_calendar.json` |
| `evidence_types` | `app_evidence_types` | 6 | `evidence_types.json` |
| `geo_city_content` | `app_geo_city_content` | 212 | `geo_city_content.json` |
| `i18n_glossary` | `app_i18n_glossary` | 609 | `i18n_glossary.json` |
| `jurisdictions` | `app_jurisdictions` | 8 | `jurisdictions.json` |
| `kg_case_verification_reports` | `app_kg_case_verification_reports` | 1 | `kg_case_verification_reports.json` |
| `kg_corridor_requirements` | `app_kg_corridor_requirements` | 6 | `kg_corridor_requirements.json` |
| `kg_corridors` | `app_kg_corridors` | 3 | `kg_corridors.json` |
| `kg_employee_types` | `app_kg_employee_types` | 4 | `kg_employee_types.json` |
| `kg_maintenance_queue` | `app_kg_maintenance_queue` | 3 | `kg_maintenance_queue.json` |
| `kg_prompt_passes` | `app_kg_prompt_passes` | 5 | `kg_prompt_passes.json` |
| `kg_requirement_sources` | `app_kg_requirement_sources` | 7 | `kg_requirement_sources.json` |
| `lawyers` | `app_lawyers` | 1 | `lawyers.json` |
| `linked_references` | `app_linked_references` | 6,421 | `linked_references.part1of2.json`<br>`linked_references.part2of2.json` |
| `notifications` | `app_notifications` | 0 _(empty)_ | `notifications.json` |
| `notion_tasks` | `app_notion_tasks` | 338 | `notion_tasks.json` |
| `obligation_confidences` | `app_obligation_confidences` | 11 | `obligation_confidences.json` |
| `obligation_dependencies` | `app_obligation_dependencies` | 7 | `obligation_dependencies.json` |
| `obligation_types` | `app_obligation_types` | 6 | `obligation_types.json` |
| `obligations` | `app_obligations` | 6 | `obligations.json` |
| `outreach_contacts` | `app_outreach_contacts` | 0 _(empty)_ | `outreach_contacts.json` |
| `pathway_eligibility_rules` | `app_pathway_eligibility_rules` | 2 | `pathway_eligibility_rules.json` |
| `pathways` | `app_pathways` | 3 | `pathways.json` |
| `person_identities` | `app_person_identities` | 5 ⚠️ **not committed — `_pii/`** | `person_identities.json` |
| `persons` | `app_persons` | 6 ⚠️ **not committed — `_pii/`** | `persons.json` |
| `pet_import_rules` | `app_pet_import_rules` | 85 | `pet_import_rules.json` |
| `programs` | `app_programs` | 7 | `programs.json` |
| `readiness_templates` | `app_readiness_templates` | 709 | `readiness_templates.json` |
| `regulatory_versions` | `app_regulatory_versions` | 2 | `regulatory_versions.json` |
| `relocation_cases` | `app_relocation_cases` | 8 | `relocation_cases.json` |
| `relocation_tasks` | `app_relocation_tasks` | 20 | `relocation_tasks.json` |
| `relopass_vendors` | `app_relopass_vendors` | 0 _(empty)_ | `relopass_vendors.json` |
| `requirement_blocks` | `app_requirement_blocks` | 63 | `requirement_blocks.json` |
| `requirement_decay_queue` | `app_requirement_decay_queue` | 0 _(empty)_ | `requirement_decay_queue.json` |
| `requirement_entities` | `app_requirement_entities` | 193 | `requirement_entities.json` |
| `requirement_facts` | `app_requirement_facts` | 755 | `requirement_facts.json` |
| `research_passes` | `app_research_passes` | 0 _(empty)_ | `research_passes.json` |
| `roadmaps` | `app_roadmaps` | 1 | `roadmaps.json` |
| `sign_offs` | `app_sign_offs` | 0 _(empty)_ | `sign_offs.json` |
| `vendor_providers` | `app_vendor_providers` | 1,825 | `vendor_providers.json` |
| `vendor_sourcing_requests` | `app_vendor_sourcing_requests` | 0 _(empty)_ | `vendor_sourcing_requests.json` |
| `vendors` | `app_vendors` | 8 | `vendors.json` |
| `verification_log` | `app_verification_log` | 12 | `verification_log.json` |

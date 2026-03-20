# Case Readiness Core v1 — audit

## Canonical entities (existing platform)

| Concept | Primary storage / linkage |
|--------|---------------------------|
| **Company** | `companies`, `relocation_cases.company_id`, `profiles.company_id`, `hr_users.company_id` |
| **HR user** | `profiles` + `hr_users`; assignment `case_assignments.hr_user_id` |
| **Employee** | `case_assignments.employee_user_id`, `employee_identifier`; profile in `employee_profiles` keyed by **`assignment_id`** |
| **Case / assignment** | **`case_assignments.id`** = assignment primary key; `case_id` / `canonical_case_id` link to `relocation_cases` / wizard case |
| **Destination** | **Canonical for readiness:** `employee_profiles.profile_json` → `movePlan.destination` or `relocationBasics.destCountry`; **fallback:** `relocation_cases.host_country` or case `profile_json` |
| **Origin** | Same profile paths: `movePlan.origin` / `relocationBasics.originCountry` |
| **Status / stage** | `case_assignments.status`, `relocation_cases.status` / `stage` (where present) |

## What this feature attaches to

- **Primary key for case state:** **`assignment_id`** (`case_assignments.id`).
- **Company scoping:** Enforced by existing **`_hr_can_access_assignment`** on all readiness endpoints (same as assignment detail).
- **Templates:** **Global** (not company-scoped): keyed by **`destination_key` + `route_key`** so one SG/employment pack serves all companies.

## Existing tables considered for reuse

- **`case_milestones` / `milestone_links`:** Operational timeline tied to `case_id`; different purpose (workflow dates). **Not reused** for Readiness Core v1 to avoid mixing curated immigration packs with ad-hoc case milestones.
- **`country_profiles` / RKG resources:** Could inform future auto-generation; **v1 is template-driven JSON seed**, not wired to those stores yet.
- **Policy / `resolved_assignment_policies`:** Separate concern (benefits); readiness is **immigration execution**, not policy caps.

## Reuse vs new

| Reuse | New |
|-------|-----|
| Assignment + HR auth + profile destination resolution | `readiness_templates`, checklist + milestone template rows |
| `employee_profiles` for destination | `case_readiness` (one row per assignment → template) |
| — | `case_readiness_checklist_state`, `case_readiness_milestone_state` (status only) |

## Duplication principle

- **No** copying template text into per-case rows.
- **Only** store: which `template_id` applies + **status / completion / notes** on checklist and milestones.

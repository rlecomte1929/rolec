# CVR labelling instructions

A CVR is evidence that a corridor can be published, and labelled training data later. It is **not** a copy of `requirement_items`. Point at ids; do not re-store citations or severity.

## `non_obvious`

Mark `is_non_obvious` / `knew_it` only for items the catalog already flags `non_obvious=true`, or that the mover volunteered as a surprise. “Non-obvious” means a competent HR generalist would not have this on their default checklist (timing windows, which agency, who can file, GP entitlement traps). It is not “long” or “annoying.”

## Severity (catalog, not CVR)

When a CVR disputes severity, record `judgment: wrong` and the action. Do not edit severity on the CVR row. Catalog severity:

- **critical / BLOCKER** — move or payroll cannot proceed; legal exposure if missed.
- **high / WARN** — likely delay, extra cost, or a hard-to-reverse admin path.
- **medium / low** — inconvenience; still cite a source.

## Source types (catalog citations)

Authoritative for serving: `statutory_law`, `government_portal`, `bilateral_agreement`, `eu_directive`. `administrative_practice` and `case_law` need counsel. A requirement without a live `source_url` is a defect, not a CVR field.

## Verdict

- **pass** — reviewer named, `requirements_missed_ids` and `requirements_wrong_ids` empty, lawyer sign-off where the template requires it.
- **fail** — any of those fail (Andrea ES→IE is fail).
- **incomplete** — session happened but ids or reviewer are missing.

## Store

Keep files under `docs/cvr/instances/`. Validate with `python3 scripts/validate_cvr.py`. No Supabase table until a product files CVRs.

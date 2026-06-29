# C1 Pilot Fixture Corpus (AIQ-511)

20 synthetic relocation dossiers for the C1 extraction / contradiction /
eligibility evaluation harness. The corpus is **materialized on demand** — the
binary PDFs and per-dossier output directories are *not* committed (see
`.gitignore`). Only the deterministic generators, the materializer, this
overview, `SCHEMA.md` and the schema tests are committed.

> **Synthetic only — PII-redacted.** Every name, employer, address, salary and
> date is derived deterministically from a seed via modulo arithmetic over fixed
> synthetic pools (`generators/base.py`). No real personal data exists anywhere
> in this corpus. The only non-deterministic value is each dossier's
> `generation_meta.generated_at` timestamp.

## Composition (20 dossiers)

| Corridor | Generator | dossier_id prefix | Count | Expected eligibility |
| --- | --- | --- | --- | --- |
| IN→DE | `in_de_generic` | `IN_DE_NNN` | 4 | `ELIGIBLE_BLUE_CARD` |
| IN→DE | `in_de_with_family` | `IN_DE_FAM_NNN` | 3 | `ELIGIBLE_BLUE_CARD` |
| IN→DE | `in_de_it_no_degree` | `IN_DE_NODEG_NNN` | 3 | `ELIGIBLE_BLUE_CARD_IT_EXPERIENCE` |
| FR→NO | `fr_no_common` | `FR_NO_NNN` | 4 | `ELIGIBLE_EU_FREE_MOVEMENT` |
| FR→NO | `fr_no_non_eea_spouse` | `FR_NO_NEEA_NNN` | 3 | `ELIGIBLE_EU_FREE_MOVEMENT` |
| FR→NO | `fr_no_french_spouse` | `FR_NO_FRSP_NNN` | 3 | `ELIGIBLE_EU_FREE_MOVEMENT` |

10 IN→DE + 10 FR→NO. FR→NO dossiers carry an EU `national_id.pdf` (instead of
passport+visa) reflecting free movement; IN→DE dossiers carry a `passport.pdf`.

## Seeded contradictions (5 of 20; the other 15 are clean)

Each of the five canonical contradiction types is seeded into exactly one
dossier — the real inconsistency is drawn into the PDFs **and** recorded in
`ground_truth.json → seeded_contradictions`.

| Dossier | Type | Inconsistency |
| --- | --- | --- |
| `IN_DE_FAM_001` | `SURNAME_MISMATCH` | passport surname ≠ diploma graduate surname |
| `IN_DE_FAM_002` | `DOB_MISMATCH` | passport DOB ≠ employment-contract DOB |
| `IN_DE_NODEG_001` | `EMPLOYER_MISMATCH` | contract employer ≠ payslip employer |
| `FR_NO_002` | `SALARY_MISMATCH` | contract salary ≠ payslip salary |
| `FR_NO_NEEA_001` | `ADDRESS_MISMATCH` | national-id address ≠ contract work address |

## Materialize

```bash
cd backend && python -m tests.fixtures.pilot.materialize --out /path/to/corpus
```

This writes 20 `<dossier_id>/` directories, each containing the PDF stubs,
`ground_truth.json`, `generation.json`, and a per-dossier `README.md`, plus a
top-level `README.md` in the output dir. Re-running is deterministic
(byte-identical apart from `generated_at`).

## Validate

```bash
cd <repo-root> && .venv311/bin/python -m pytest backend/tests/fixtures/pilot/test_schema.py -q
```

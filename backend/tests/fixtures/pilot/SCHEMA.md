# Pilot Corpus Dossier Layout

Each synthetic dossier lives in a directory named by its `dossier_id`:

```
<dossier_id>/
  ground_truth.json    # Dossier model as JSON
  generation.json      # GenerationMeta
  passport.pdf         # Synthesized via reportlab
  employment_contract.pdf
  payslip_01.pdf
  payslip_02.pdf
  payslip_03.pdf
  diploma.pdf
```

## Field descriptions

- `ground_truth.json` — Full `Dossier` model serialised to JSON. Contains `extracted_fields`, `canonical_entities`, `eligibility_verdict`, `step_graph`, `seeded_contradictions`, and `generation_meta`.
- `generation.json` — `GenerationMeta` only; kept as a lightweight sidecar so tooling can read seed/schema_version without parsing the full dossier.
- PDF files — Minimal 1-page stubs generated deterministically from the seed value via reportlab. Each page contains the relevant text fields drawn at known positions so bbox ground-truth is reproducible.

## Corridor

The initial pilot corpus covers the **IN→DE Blue Card** scenario (`in_de_generic` generator, seeds 1–50).

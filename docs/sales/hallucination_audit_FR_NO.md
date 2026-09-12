# Hallucination audit — FR→NO (catalog-grounded first pass)

**Date:** 2026-09-12  
**Corridor:** FR→NO (French / EEA national employed in Norway)  
**Ground truth:** `docs/imports/corridor-facts-2026-09-08/src/fr-no-facts.ndjson` plus served `requirement_items` for Norway.  
**Live frontier-model paste:** not run in this commit. Before Demo Day, paste GPT-4o / Claude / Gemini outputs into the table below against the same prompt.

## Prompt

> What are all the administrative, immigration, tax, and social security requirements for a French national moving to Norway for work, employed by a French company? Please include all deadlines and non-obvious requirements.

## Named misses ReloPass already encodes (use these in the pitch)

| Name | ReloPass fact | Typical LLM miss | Consequence |
|---|---|---|---|
| **The D-number gap** | You cannot apply for a D-number yourself; an enterprise or authority requests it (`fr-no-res-005`). | “Go to Skatteetaten and apply for a D-number.” | Payroll and banking stall while HR waits on the wrong actor. |
| **The fastlege trap** | D-number holders are not entitled to a regular GP (`fr-no-hc-002`). | “Register with a GP when you arrive.” | Employee has no fastlege and discovers it at first illness. |
| **Police, not UDI** | Stay >3 months: register with the **police**; French nationals are not Nordic-exempt (`fr-no-imm-002`). | “Register with immigration / UDI.” | Appointment booked at the wrong agency; slots fill weeks ahead. |
| **PAYE auto-enrol** | New tax-card applicants are enrolled in PAYE by default (`fr-no-tax-002`). | Generic “get a skattekort” with no scheme. | Unexpected 25% withholding; no tax return when they expected one. |

## Protocol for a live model run

1. Submit the prompt to each model with default settings (and once with max reasoning budget — RP-K-019, same log).
2. Score **recall** against the FR→NO verified list (not against the model’s own citations).
3. Alert if any model exceeds **85% recall** on that list — the sales story changes; the serving architecture does not.

Do not claim EU AI Act status in the write-up.

## ES→IE / NO→FR

ES→IE Andrea CVR already failed on missed/wrong requirements (`docs/cvr/instances/es-ie-2026-08-15-andrea.json`). NO→FR has no session (`no-fr-placeholder.json`). Do not invent scores for those corridors.

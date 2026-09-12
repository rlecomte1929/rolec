# IE→ES launch gap — 2026-09-12

**Corridor id:** `IE_ES` (registry) / `IE-ES` (batch alias)
**Legal shape:** Irish (EU) national → Spain, free movement. Mirrors `FR_ES` / `ES_FREEMOVE_2026`, not `ES_IE`.
**Anchor:** Dublin → Madrid. No completed CVR.
**This note:** research inventory only. Candidates stay `pending`. No approval, no §6 CVR fill.

## What is already authored

| Asset | Status vs serving |
|---|---|
| Registry + pathway `ES_FREEMOVE_2026` | Present. Representative. |
| 25 NDJSON facts (`corridors/IE_ES/data/ie_es_requirement_facts.ndjson`) | Authored, sha256-pinned. Load SQL written (`20261108000000_ie_es_requirement_items.sql`). |
| `review_status` | All **pending**. `requirements_builder` serves approved only → **nothing served**. |
| Production apply | Migration **not applied**. |
| CVR | Template only: `docs/corridors/ie-es/CVR-TEMPLATE.md`. **§6 Relief moment is human. Do not invent it.** |

## Gap table — what blocks approved, served facts

| # | Gap | Blocking? | Who |
|---|---|---|---|
| 1 | Load not on prod | Yes — no rows to approve | Operator / Claude Code |
| 2 | All 25 still `pending` | Yes — even after apply, nothing serves until a human flips status | Human reviewer at `/admin/countries` |
| 3 | `tax_residency_183_days` and `tax_ie_es_double_taxation` claim the **Ireland–Spain treaty tie-breaker** while citing the **AEAT residency page**, not the treaty text | Yes for those two — `needs_lawyer_review`. Must not be approved until counsel cites the convention | Counsel |
| 4 | Human CVR (template §§1–7, including **§6 relief moment**) | Yes for “verified / launch-ready”. Authored ≠ verified | Human session (AIQ-2313). Otto does not fill §6 |
| 5 | Two dead-link / evidence refresh items already named in the campaign plan (SPAIN 404s) | Re-source before approval if the cited URL no longer resolves | Otto re-fetch, then human |

## Official sources to fetch (allowlisted hosts)

Do not invent quotes. Fetch the publisher page; copy a verbatim sentence; land `pending` / `representative`.

| Topic already in the batch | Official host to re-fetch before approval |
|---|---|
| Certificado de registro UE / EX-18 / tasa 790-012 | `sede.policia.gob.es`, `inclusion.gob.es`, `interior.gob.es` |
| NIE | `interior.gob.es`, `policia.es` / `sede.policia.gob.es` |
| Padrón (Madrid) | `madrid.es` (`sede.madrid.es`) |
| IRPF 183-day residency, Modelo 030, Beckham / Modelo 149 | `agenciatributaria.es` / `agenciatributaria.gob.es` (suffix + host both official) |
| IE–ES treaty tie-breaker (the two lawyer-flagged rows) | Treaty text, not the AEAT residency landing page. Prefer the official convention text on an official host (`boe.es` if published there, or the Irish Revenue / Irish statute host that carries the convention). **Until that page is fetched and quoted, keep `needs_lawyer_review`.** |
| NUSS / alta | `seg-social.es` (Importass) |
| Single-state / A1 | Prefer `eur-lex.europa.eu` (Reg. 883/2004) or a statutory liaison page. `youreurope.europa.eu` is **semi-official** — keep, do not auto-accept |
| SNS / TSI | Comunidad / SNS official pages already cited in the batch — re-resolve before approve |
| DGT / licence | `dgt.es` is a Spanish statutory body; confirm it is on the importer allowlist before a new candidate cites it |

## What Otto will not do on this corridor

- Fake CVR §6 or mark the corridor verified.
- Flip any `review_status` to approved.
- Unpark Ireland PPS pillar cards (2196–2199) or vendor / departure farms.

## Human CVR still required

**Yes — the entire IE→ES CVR, including §6.** The 15 non-obvious rows in the template are the question set. Counsel sign-off on the two treaty rows is a separate red gate inside that CVR.

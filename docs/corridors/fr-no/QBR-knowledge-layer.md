# FR→NO knowledge-layer QBR stub

Golden corridor for the knowledge-domain scorecard: **France → Norway** (`FR_NO` /
catalog destination `NORWAY`). Steal McKinsey’s **five columns**, not their
percentages. Live production counts are **N/A** until an operator fills them from
a read-only query; do not invent a baseline of 100.

In-repo seed baseline (not production): `backend/seeds/requirements/norway.yaml`
scored by `scripts/knowledge_layer_baseline.py`. That script never talks to prod.

| Column | ReloPass metric | This stub |
|---|---|---|
| **Adoption (input)** | % of target FR→NO cases that open the dossier; % of those items with a visible citation | **N/A** — no named HR segment / case sample in this checkout |
| **Quality (output)** | Citation resolve rate; pending-not-served; first-pass issues; serving/LLM isolation | Isolation: CI gate. Catalog quality: run the baseline script. Live pending vs approved: **N/A** without a DB read |
| **Satisfaction (output)** | Policy Assistant helpfulness if sample ≥ ~10% of users | **N/A** — sample too small to claim NPS; do not use ambition >75 |
| **Productivity (output)** | Hours from staging → approved promote | **N/A** — not measured; never the headline |
| **Financial (output)** | Paying or expansion cases on a *sufficient* FR→NO catalog; employers retained | **N/A** — no Finance OKR attached here |

**Phase:** baseline (index not invented). Weeks 1–4 are a citation/country-key pilot, not a
“rewired” claim.

**Falsifiers:** empty dossier on a sold FR→NO case; citation resolve rate falling; serving/LLM
isolation red; a served row with no human promote; invented citations.

**Headline that passes the 80/6 test:** “FR→NO SQLs / cases used a sufficient, cited catalog”
— not “AI improved productivity.”

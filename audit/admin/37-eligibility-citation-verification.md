# 37 — Eligibility Eval: Legal-Citation Verification Worksheet

**Corridors:** `us_fr` (US → France) and `br_pt` (Brazil → Portugal)
**Date:** 2026-06-30
**Author:** AI-researched draft (Claude) — read-only pass over fixtures; no fixtures or code modified.

---

## ⚠️ HONESTY NOTE — READ FIRST

The citations proposed below are **AI-researched candidates produced from public web sources
(Légifrance, Diário da República / PGDL, AIMA). They are NOT legal advice and have NOT been
signed off by a qualified immigration lawyer.** Treat every row as *"best current candidate,
pending legal confirmation."*

- I can confirm with **HIGH confidence that the article *numbers* asserted in the current
  synthetic citations are real, governing provisions that still exist** (FR CESEDA L.421-1;
  PT Lei 23/2007 art. 88).
- What I **cannot** verify from web research alone, and what genuinely needs a lawyer:
  1. The **version/effective-year suffix** baked into each citation ID (`:2024`, `:2007`) —
     these do not map cleanly to a specific amendment I can pin down.
  2. The **exact sub-article / route choice** for a *long-term assignment (LTA)* — French and
     Portuguese law each offer several adjacent routes (salarié vs ICT vs talent; art. 88 n.º 1
     vs n.º 2), and which one the corridor *intends* is a product/legal decision, not a fact I
     can read off a statute.
- Web search is point-in-time and can lag or miss a recent amendment. Légifrance and Diário da
  República are the authoritative primary sources; the URLs below should be opened and the
  in-force ("en vigueur" / "versão atual") text confirmed on the day of sign-off.

Both corridors contain exactly **one** eligibility case each (a single synthetic dossier with a
single `outcome_set`), so there are **2 cases total** to verify.

---

## Corridor: `us_fr` (United States → France)

**Source files:**
- `backend/tests/fixtures/eligibility/us_fr/ground_truth.json`
- `backend/eval/rule_registry.py` (line ~32: `"FR_CESEDA_L421:2024"`)

### Case 1 — American national, LTA, France

| Field | Value |
|---|---|
| Profile | nationality American; origin US; destination France; contract_type `lta` |
| Outcome (`outcome_set`) | `ELIGIBLE_WORK_PERMIT` |
| Eligibility route asserted | Standard French work/residence permit — carte de séjour temporaire mention **"salarié"** (per fixture `_meta.note`) |
| **Current (synthetic) citation** | `FR_CESEDA_L421:2024` → "CESEDA art. L.421-1 ff., 'salarié' work/residence permit" |

**Proposed real citation:** **CESEDA art. L.421-1** (Code de l'entrée et du séjour des étrangers
et du droit d'asile) — *"L'étranger qui exerce une activité salariée sous contrat de travail à
durée indéterminée … se voit délivrer une carte de séjour temporaire portant la mention
'salarié'."*

- **Source:** Légifrance, Article L421-1 — https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000042776797
  (section "Étranger exerçant une activité salariée", arts. L421-1 to L421-4:
  https://www.legifrance.gouv.fr/codes/section_lc/LEGITEXT000006070158/LEGISCTA000042771542/ )
- **Confidence (article number = L.421-1):** **HIGH** — verified on Légifrance; the article
  exists, is in force, and is exactly the "salarié" CDI residence-card provision the fixture
  describes.
- **Confidence (full citation as written, incl. `:2024`):** **LOW / UNVERIFIED.**

**What Romain must confirm:**
1. **Version year `:2024` is unverified.** The L.421-x numbering came into force on **1 May
   2021** via Ordonnance n° 2020-1733 of 16 Dec 2020 (recodification). I could **not** identify
   a 2024 amendment that re-versions L.421-1. Recommend changing the suffix to **`:2021`** (the
   recodification in-force date) *unless* a specific 2024 reform is intended — confirm with
   counsel. The `rule_registry.py` window currently sets `effective_from = 2024-01-01`, which is
   **almost certainly wrong**; the provision has been in force since **2021-05-01**.
2. **Sub-article / route for an LTA.** L.421-1 is the **CDI ("salarié")** card. For a long-term
   *assignment*, the apt provision may instead be:
   - **L.421-3** — "travailleur temporaire" (fixed-term/CDD), or
   - **L.421-26 ff.** — "salarié détaché ICT" (intra-corporate transferee, EU Directive
     2014/66/EU), often the correct route for an intra-group secondment, or
   - **L.421-9 ff.** — "passeport talent" (e.g. salarié qualifié / EU Blue Card) if the role is
     highly qualified.
   Decide which route the `us_fr` corridor is meant to model and confirm the matching article.
   The current fixture deliberately models the **plain "salarié"** route, so L.421-1 is internally
   consistent — but verify that is the intended scenario for an LTA.
3. Confirm whether the citation should reference the **R.** (regulatory, e.g. R.421-1) companion
   articles for procedure, or stay at the **L.** (legislative) level.

---

## Corridor: `br_pt` (Brazil → Portugal)

**Source files:**
- `backend/tests/fixtures/eligibility/br_pt/ground_truth.json`
- `backend/eval/rule_registry.py` (line ~34: `"PT_LEI_23_2007_ART88:2007"`)

### Case 1 — Brazilian national, LTA, Portugal

| Field | Value |
|---|---|
| Profile | nationality Brazilian; origin Brazil; destination Portugal; contract_type `lta` |
| Outcome (`outcome_set`) | `ELIGIBLE_WORK_PERMIT` |
| Eligibility route asserted | Standard residence permit for **subordinate (employed) professional activity** (per fixture `_meta.note`) |
| **Current (synthetic) citation** | `PT_LEI_23_2007_ART88:2007` → "Lei n.º 23/2007 art. 88, subordinate-work residence permit" |

**Proposed real citation:** **Lei n.º 23/2007, de 4 de julho, artigo 88.º** —
*"Autorização de residência para exercício de atividade profissional subordinada"* (residence
permit for the exercise of subordinate professional activity).

- **Sources:**
  - Diário da República, Lei n.º 23/2007 — https://diariodarepublica.pt/dr/detalhe/lei/23-2007-635814
  - PGDL (consolidated, art. 88) — https://www.pgdlisboa.pt/leis/lei_mostra_articulado.php?artigo_id=920A0088&nid=920&tabela=leis
  - AIMA (current immigration authority) "Art. 88.º, n.º 1" (with residence visa) —
    https://aima.gov.pt/pt/trabalhar/autorizacao-de-residencia-para-exercicio-de-atividade-profissional-subordinada-com-visto-de-residencia-art-88-o-n-o-1
    and "Art. 88.º, n.º 2" (visa-exempt) —
    https://aima.gov.pt/pt/trabalhar/autorizacao-de-residencia-para-exercicio-de-atividade-profissional-subordinada-com-dispensa-de-visto-de-residencia-art-88-o-n-o-
- **Confidence (article number = art. 88.º, subordinate-work residence permit):** **HIGH** —
  corroborated by three independent sources including AIMA (the live government immigration body)
  and the official Diário da República. The article number and its subject matter are correct and
  current.
- **Confidence (full citation as written, incl. `:2007`):** **MEDIUM.**

**What Romain must confirm:**
1. **The `:2007` version suffix is the *original enactment* year, not the current consolidated
   text.** Lei 23/2007 has been amended many times; art. 88 specifically was touched by recent
   reforms — **Decreto-Lei n.º 37-A/2024 (3 June 2024)** revoked the "manifestação de interesse"
   route, and **Lei n.º 40/2024 (7 Nov 2024)** added transitional safeguards referencing
   **art. 88 n.º 6**. So the *governing text today is the consolidated version as amended through
   2024*, not the 2007 original. Decide whether the version tag should remain `:2007` (date of the
   base law) or move to the latest amendment (e.g. `:2024`). Confirm with counsel which convention
   the eval intends.
2. **Sub-number (n.º 1 vs n.º 2).** For a corporate LTA where the assignee enters Portugal on a
   **residence visa** obtained abroad, the precise pointer is **art. 88.º n.º 1**. Art. 88.º n.º 2
   is the **visa-exempt / already-in-territory** path (heavily curtailed by DL 37-A/2024). The
   current citation points to "art. 88" generically — confirm whether to pin it to **n.º 1**.
3. **Highly-qualified alternative.** If the Brazilian assignee is highly qualified, the intended
   route might instead be the **EU Blue Card — "Cartão Azul UE", art. 61.º-A / 121.º-A ff.** of
   Lei 23/2007 (transposing EU Directive 2021/1883), not art. 88. Confirm the corridor models a
   *standard* subordinate-work permit (art. 88) and not the Blue Card.
4. **CPLP note (optional, for product accuracy):** Brazilians benefit from CPLP-specific
   facilitations (Acordo de Mobilidade CPLP; art. 88-A-style provisions / special CPLP residence
   permits). This does not change the art. 88 baseline but may be the *more accurate* route for a
   Brazilian national in practice — flag for counsel.

---

## Summary

| Corridor | Cases | Article number verified | Full citation status |
|---|---|---|---|
| `us_fr` | 1 | **HIGH** — CESEDA L.421-1 is real, in force, matches "salarié" route | Version suffix `:2024` **UNVERIFIED** (likely should be `:2021`); sub-article/route for LTA needs a product+legal decision |
| `br_pt` | 1 | **HIGH** — Lei 23/2007 art. 88.º is real, current, confirmed by AIMA | Version suffix `:2007` = base-law year only (amended through 2024); pin to n.º 1 and confirm vs Blue Card / CPLP |

**Bottom line:** 2 cases total. For **both**, the *governing article number* can be proposed with
**HIGH confidence**. For **neither** can the *complete citation string as currently written* be
certified without legal sign-off — the unresolved pieces are (a) the version-year suffix and (b)
the precise sub-article/route mapping for a long-term assignment. No citation here should be
treated as authoritative until a qualified immigration lawyer confirms it against the in-force
primary-source text on Légifrance and Diário da República.

### Recommended `rule_registry.py` follow-ups (for Romain to action, not applied here)
- `FR_CESEDA_L421:2024` → the `effective_from = date(2024, 1, 1)` window is almost certainly
  wrong; the L.421 recodification took effect **2021-05-01**. Reconcile the version tag and the
  effective date together.
- `PT_LEI_23_2007_ART88:2007` → effective_from `2007-08-04` is plausible for the base law, but the
  *current* art. 88 text reflects 2024 amendments; decide whether to version it as the base law or
  the latest amendment.

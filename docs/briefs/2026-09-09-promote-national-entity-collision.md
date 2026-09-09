# Scoped fix brief — `promote()` mis-attaches national entities of multinationals

**Surface:** vendor-candidate landing pipeline (results tracked on PR #2194).
**Files:** `backend/imports/suppliers/executor.py` (`promote()`), `backend/app/services/vendor_harvester.py` (`_name_key`).
**Severity:** correctness / data integrity — but **narrow** (see §1a) and now guarded by a pre-apply predictor (§5). Silent mis-attach of a supplier capability to the **wrong legal entity** when two names collide after normalization.

---

## 1. Symptom (observed 2026-09-09)

Promoting the Madrid-banks batch, candidate **"Banco Santander, S.A."** (Spain, BdE código 0049) was
promoted **onto the existing "Banco Santander (Brasil) S.A." supplier** — the Spanish banking
capability attached to the Brazilian entity. It was caught, the mis-created pending capability
deleted, the candidate reset, and **Santander Spain held** for a correct re-land. Net: the batch
landed **+6 not +7**.

## 1a. Scope correction — it is NARROWER than "every multinational" (verified 2026-09-09)

The initial worry was that this hits every national arm of a multinational. It does **not**. Verified
on the Milan-banks land: **"Deutsche Bank S.p.A." (IT) did NOT collide with "Deutsche Bank, S.A.E."
(ES)**, and all 7 IT banks promoted to new suppliers with zero collisions. The reason is how `_name_key`
strips legal forms: it removes only tokens in `_LEGAL_FORMS`. `"S.A."` → `"sa"` **is** in that set and is
stripped; `"S.p.A."` → `"spa"` and `"S.A.E."` → `"sae"` are **not**, so they survive as name tokens:
`deutschebankspa` ≠ `deutschebanksae`. Santander collided only because its two forms —
`"Banco Santander, S.A."` and `"Banco Santander (Brasil) S.A."` — **both** reduce to `bancosantander`
(", S.A." stripped, "(Brasil)" dropped).

**The bug fires only when two genuinely different entities produce the SAME `_name_key`** — i.e. when a
`_LEGAL_FORMS` suffix is stripped *and/or* a distinguishing parenthetical is dropped, leaving identical
tokens. That is a real but uncommon coincidence, not a per-batch certainty. Treat this as a **correctness
fix of moderate priority**, not an urgent every-bank blocker — especially given the pre-apply guard in §5.

## 2. Root cause (exact)

`promote()` matches a candidate to an existing supplier by **normalized name only**, ignoring country:

- `backend/imports/suppliers/executor.py:301-308` builds `existing: Dict[name_key -> supplier_id]`
  from **all** suppliers (name + legal_name), no country in the key.
- `:322` `if key in existing:` → attach a capability to that supplier via `add_capability`.
- The key comes from `_name_key` (`backend/app/services/vendor_harvester.py:102`), whose
  `:125  re.sub(r"\([^)]*\)", " ", folded)` **drops all parenthetical asides**. So
  `_name_key("Banco Santander (Brasil) S.A.")` == `_name_key("Banco Santander, S.A.")` ==
  `"bancosantander"`. Collision → the ES candidate resolves to the BR supplier.

**This is DELIBERATE, and correct for movers.** The `_name_key` docstring
(`vendor_harvester.py:108-116`) states it on purpose:

> "'Crown Relocations (Norway)' also collapses onto 'Crown Relocations'… a supplier holds many
> per-country capabilities, so one Crown with a Norway capability is more correct than two Crown rows."

For **global mover networks** (Crown, AGS, FIDI affiliates) one brand == one supplier with per-country
capabilities — collapsing is right. For **nationally-incorporated entities** (banks; and by the same
logic nationally-licensed professions — `legal_admin`, `tax_finance`) the national arms are **distinct
legal entities that merely share a brand**, and collapsing is wrong.

**So the fix must fix banks WITHOUT regressing movers.** A naive "add country to the key" change would
create a second Crown supplier for every corridor — the exact bug the current behavior prevents.

## 3. Recommended fix — category + country-aware collapse

Gate the collapse by whether the match is plausibly the *same legal entity*:

In the `if key in existing:` branch of `promote()` (`executor.py:322`), before attaching a capability:

1. Look up the matched supplier's existing capability **country_codes** (the capability model already
   stores `country_code`, set at `executor.py:235`). Add that to the `existing` index, or query on match.
2. **Collapse (add capability) when** the candidate is plausibly the same entity:
   - the matched supplier **already has a capability in the candidate's `country_code`** (`row["country_code"]`), **OR**
   - the candidate's category is a **global-network category** (default; `movers` is the canonical case).
3. **Do NOT collapse — create a distinct supplier instead — when** the category is a
   **national-entity category** (`banks`, `legal_admin`, `tax_finance`) **and** the matched supplier has
   **no** capability in the candidate's country. That is the Santander-ES-vs-Santander-BR case.

Introduce one small constant, e.g. `NATIONAL_ENTITY_CATEGORIES = {"banks", "legal_admin", "tax_finance"}`
(easy to tune; keep it conservative). Everything not in it keeps today's collapse behavior.

Edge case to preserve: a national-entity supplier legitimately expanding to a new corridor **within the
same country** (e.g. a Spanish bank gaining an ES→FR capability) still has a capability in that country,
so rule 2's first clause collapses it correctly — no false split.

### Alternative considered (not recommended as primary)
Make `_name_key` **retain** a parenthetical that names a country/nationality (keep "(Brasil)", drop
"(SOFDI)"). Rejected: needs a country/nationality-name detector, is fragile, and changes the shared
dedupe key used everywhere (`vendor_harvester` dedupe fallback), risking movers regressions far from
this code path. The category+country gate is local to `promote()` and testable in isolation.

## 4. Guardrail tests (both directions — a fix that only does one is wrong)

Add hermetic tests (no real DB — follow `scripts/tests/test_import_supplier_candidates_scope.py` fakes):

1. **FIXES banks:** existing supplier "Banco Santander (Brasil) S.A." (BR capability). Promote candidate
   "Banco Santander, S.A." country_code=ES, category=banks → a **new supplier** is created (or the row is
   held/flagged), the capability is **NOT** attached to the BR supplier. `promoted_supplier_id != BR id`.
2. **NO movers regression:** existing supplier "Crown Relocations" (a movers supplier). Promote candidate
   "Crown Relocations (Norway)" category=movers → capability **IS** added to the existing Crown supplier
   (one supplier, per-country capabilities). Current behavior unchanged.
3. **Same-country expansion still collapses:** existing "Banco X" with an ES capability; promote "Banco X"
   country_code=ES, new corridor, category=banks → capability added to the existing Banco X (not a dup).
4. **AGS aside still collapses:** "AGS France (SOFDI – …)" vs "AGS France (SOFDI)", category=movers →
   one supplier. (Protects the original `_name_key` intent.)

## 5. Interim guard (already in place — keep until the fix lands)
The operator now runs a **pre-apply `_name_key` predictor**: for each candidate, compute the exact
`_name_key` and check it against every prod supplier's key *before* promoting; a match is inspected
(country vs candidate country) and held/corrected if it is a distinct legal entity. This catches real
collisions **before** they write — no more apply-then-delete — and is what confirmed the Milan-banks
batch was collision-free. This guard is the reason the code fix is moderate- rather than high-priority.
Keep it until the fix + tests below land; the fix makes `promote()` correct on its own so the predictor
can then relax to a sanity check.

## 6. Scope boundaries (do NOT do)
- No change to `movers` behavior or to the broader `_name_key` semantics.
- No new migration / schema change — capabilities already carry `country_code`.
- No touching the corridor-facts pipeline (`requirement_items`) — this is the vendor/supplier path only.
- Keep `NATIONAL_ENTITY_CATEGORIES` conservative (banks + the two licensed professions); expanding it is
  a follow-up, not this fix.

## 7. Acceptance
- All four tests in §4 pass.
- A re-run of the held **Santander Spain** candidate promotes to a **distinct** supplier (código 0049,
  ES), leaving Santander Brasil untouched.
- `pytest backend/imports/suppliers` + `scripts/tests/test_import_supplier_candidates_scope.py` green.
- Append-only invariants of `promote()` (idempotent on `promoted_supplier_id`) unchanged.

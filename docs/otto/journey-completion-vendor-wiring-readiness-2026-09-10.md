# Journey-completion vendor wiring — readiness map (2026-09-10)

Investigation output from the overnight pass. The goal was to build the reusable Claude-Code
wiring ahead of Otto's data. On investigation, the "new service categories" turn out to be a
**cross-cutting change to the provenance-gated vendor pipeline**, not contained additive
scaffolding — it touches three separate category allowlists, coverage semantics for all 64
corridors, and a pinned test invariant, and it surfaced real bugs in the Otto vendor prompts. So
rather than push a blind, unattended change to the repo's most provenance-sensitive area (the one
`CLAUDE.md` flags as "too narrow three times"), this note captures exactly what to change so the
morning execution — **with Otto's delivered CSVs in hand to confirm the exact cited hosts** — is
fast and correct.

**Not affected (load cleanly today):** the **FACTS** batches (A-P1, A-P10, D-P1, D-P10, AD-P1,
AD-TAX, AD-P10, AB-P1, AB-P10) via `check_otto_batches.py` + `import_otto_facts.py`, and the
**RESOURCES** batches (A-P2, A-P5, D-P2, D-P5, AD-P2, AD-P5, AB-P2, AB-P5) via
`import_resources.py --bundle`. Neither path uses `service_category` or the vendor allowlists.
So Andrea's pipe can be validated end-to-end on **A-P1** first with none of the wiring below.
Only the **VENDOR** batches (A-P3/P4/P6/P7/P9 and the corridor equivalents) need this.

---

## 1 · Bugs in the Otto vendor prompts (fix these first — cheapest)

The `service_category` values in the batch-prompts doc don't all match the system's accepted
vocabulary. `backend/app/services/supplier_validation.py::VALID_SERVICE_CATEGORIES` rejects a row
whose `service_category` isn't in its set, and the recommendation plugin keys
(`backend/app/recommendations/plugins/`) are the canonical backend keys.

| Prompt used | System status | Action |
|---|---|---|
| `medical` | ✅ valid (`VALID_SERVICE_CATEGORIES`, plugin `medical`) | none |
| `tax_finance` | ✅ valid | none |
| `language` | ❌ system key is **`language_integration`** | **rename in prompts → `language_integration`** (A-P6, D-P6, AB-P6) |
| `temp_accommodation` | ❌ in no allowlist, no plugin | new category — see §2 (A-P3, D-P3, AD-P3, AB-P3) |
| `spouse` | ❌ in no allowlist, no plugin | design decision — new category vs `general` fallback — see §3 (A-P7, D-P7, AD-P7, AB-P7) |

`drivers_license` is not affected — those packages (A-P5, D-P5, AD-P5, AB-P5) are **RESOURCE
bundles** (`category_key:'transport'`), not vendor CSVs.

**Corridor codes:** the prompts use `XX-IE / XX-FR / XX-SG / XX-EC` for city-level vendors, but
`registry_sources.CORRIDORS` has only `ES-IE / NO-FR / FR-SG / US-EC` (no `XX-*` for these).
Confirmed harmless for loading — neither `supplier_validation` nor `import_supplier_candidates.py`
validates the corridor token, and `source_for_url()` ignores it. But `RegistrySource.corridors`
**must** use the real codes (its `__post_init__` rejects an unknown corridor). Decide morning:
either have Otto emit the real corridor code, or add `XX-IE/XX-FR/XX-SG/XX-EC` to `CORRIDORS`.

---

## 2 · Adding a new service category is a cross-cutting change (not additive scaffolding)

A new category (e.g. `temp_accommodation`) must be added **consistently** across all of these, or
it half-works:

| Location | Role | Effect of adding |
|---|---|---|
| `backend/app/services/registry_sources.py::CATEGORIES` | harvest scope + `RegistrySource.__post_init__` gate (a source can't reference an unknown category) | required before any `RegistrySource` can cite the category |
| `backend/app/services/supplier_validation.py::VALID_SERVICE_CATEGORIES` | row-acceptance gate | required or every row rejects |
| `backend/app/services/coverage_service.py` (`SERVING_CATEGORIES`) | coverage report `by_cat` / `serving_categories` | coverage now reports the new category for **all** corridors |
| `backend/app/services/accreditation_hardening.py::IN_SCOPE_CATEGORIES` | which categories require accreditation hardening (`legal_admin, movers, housing_agencies, tax_finance`) | decide whether temp housing needs it (probably not) |
| `backend/app/recommendations/plugins/` + `registry.py` | serving the category to the employee | no plugin exists for `temp_accommodation`/`spouse` — a tile with no plugin serves nothing |

**Blast radius to respect:** `pairs_in_scope() = CORRIDORS × CATEGORIES`. Adding 1 category grows
it by 64 pairs (one per corridor), and `backend/tests/test_vendor_harvester.py::
test_pairs_in_scope_is_corridors_x_categories` **hard-asserts `== 384`** (64×6). Any category
addition must update that literal (and the assertion stays `len(CORRIDORS)*len(CATEGORIES)`, so its
intent is preserved). This is why it can't be done as a quiet one-liner.

---

## 3 · `spouse` needs a decision, not a guess

There is no `spouse` plugin and no `spouse` in any allowlist. The dual-career / spouse-employment
vendors (A-P7 etc.) have three defensible homes — pick one deliberately in the morning:
- map the vendor `service_category` to **`general`** (the existing `VALID_SERVICE_CATEGORIES`
  fallback) and carry "spouse career" in a tag/note; simplest, no new category;
- add a new **`spouse_employment`** category across §2's allowlists + a plugin; most correct, most work;
- defer P7 vendors entirely for the first pass (the plan already treats spouse as lower priority,
  and spouse **immigration** facts already exist for ES-IE).

Recommendation: `general` for the first pass; revisit if the tile is prioritised.

---

## 4 · Register-host allowlist (`backend/imports/suppliers/parsers.py::_DOMAIN_TO_SOURCE`)

Even a valid-category row **rejects as `SELF_DECLARED` (tier 3)** unless its `source_url` host is in
`_DOMAIN_TO_SOURCE` mapped to a `RegistrySource` name that exists in `SOURCES`. Adding an official
register is the **safe direction** — it can only fix the "allowlist too narrow" problem, never
launder a vendor's own site. Pattern to follow (matches how the IE/FR/SG statutory registers were
already added): `PUBLIC_REGISTER`, **tier 2**, staged `claimed`, human-confirmed at
`/admin/vetting-queue`; no `entry_url_pattern` needed. Each addition is **two edits**: a
`RegistrySource(...)` in `SOURCES` (registry_sources.py) **and** a `(host, name)` in
`_DOMAIN_TO_SOURCE` (parsers.py) whose name matches.

Registers the Otto prompts name, by corridor × new category. **Confirm each exact host against the
`source_url` Otto actually cites in the delivered CSV before adding** — an omission rejects a good
row (recoverable), a wrong host is inert. Confidence is my estimate of the base domain:

| Corridor | Category | Register (from prompt) | Host (confirm vs delivered CSV) | Conf. |
|---|---|---|---|---|
| ES-IE | medical | Irish Medical Council / ICGP / HSE find-a-GP | `medicalcouncil.ie`, `icgp.ie`, `hse.ie` | high / med / high |
| ES-IE | temp_accommodation | Fáilte Ireland / CRO | `failteireland.ie`, `cro.ie` | med / high |
| ES-IE | language_integration | ACELS / QQI IEM | `qqi.ie` | high (ACELS host uncertain) |
| ES-IE | tax_finance | Irish Tax Institute / Chartered Accountants Ireland | `taxinstitute.ie`, `charteredaccountants.ie` | high (note: `cpaireland.ie` already mapped) |
| NO-FR | medical | Ordre des Médecins / ameli annuaire santé | `conseil-national.medecin.fr`, `ameli.fr` | high |
| NO-FR | temp_accommodation | SIRENE/INSEE / Atout France | `annuaire-entreprises.data.gouv.fr` | high |
| NO-FR | language_integration | Label Qualité FLE / Qualiopi | `qualitefle.fr` | med |
| FR-SG | medical | SMC / MOH clinic directory | `moh.gov.sg` (SMC host uncertain) | high |
| FR-SG | temp_accommodation | URA / ACRA / STB | `ura.gov.sg`, `stb.gov.sg` (`acra.gov.sg` already mapped) | high |
| US-EC | medical | ACESS / MSP | `salud.gob.ec` (ACESS host uncertain) | high |
| US-EC | temp_accommodation | Min. Turismo catastro / SRI RUC | `turismo.gob.ec`, `sri.gob.ec` | high |
| US-EC | banks (AB-CORE) | Superintendencia de Bancos | `superbancos.gob.ec` | high |
| US-EC | schools (AB-CORE) | Min. Educación / IB | `educacion.gob.ec` (`ibo.org` already mapped) | high |
| US-EC | legal_admin (AB-CORE) | Consejo de la Judicatura / Foro de Abogados | `funcionjudicial.gob.ec` | high |
| US-EC | tax_finance (AB-CORE) | Colegio de Contadores | host uncertain — confirm vs CSV | low |
| US-EC | language_integration | SETEC / SRI / Instituto Cervantes | `sri.gob.ec` (SETEC/Cervantes hosts uncertain) | med |

---

## 5 · Recommended morning sequence

1. **Validate the pipe on FACTS first** — Andrea **A-P1** (`es-departure-2026-09-10`):
   `check_otto_batches.py` → `import_otto_facts.py` dry-run (expect 100% promote, 0 unmapped) →
   `--apply` as candidate. Needs none of the wiring above; proves the whole tandem loop.
2. **Fix the prompt vocabulary** (§1): rename `language` → `language_integration`; decide `spouse`
   (§3); decide the corridor-code question. Relay the corrections to Otto.
3. **Do the vendor wiring as one reviewed change** (§2 + §4), against the delivered CSVs so the
   exact `source_url` hosts are confirmed, not guessed. Add `temp_accommodation` (+ chosen `spouse`
   home) across all of §2's allowlists in one commit, update the `384` test literal, add the §4
   register hosts, and run `test_vendor_harvester.py` + the supplier parser tests + a new test
   asserting each added host maps off `SELF_DECLARED`.
4. **Load RESOURCES** (A-P2, A-P5) — unaffected, load anytime with `--mode draft_only`.

Everything lands candidate-only; a human reviewer/counsel promotes to live.

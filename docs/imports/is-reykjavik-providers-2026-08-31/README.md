# Reykjavík / Iceland service providers — register-evidenced sourcing

**Corridor tag:** `XX-IS` (every row)
**Date:** 2026-08-31
**Rule:** every row is evidenced by an official statutory register / accreditation body page
(`source_url`), never the firm's own marketing site. Categories with no reachable official
per-firm register are SKIPPED rather than filled with self-declared firms.

Iceland is a small market; a partial set (banks + schools + audit firms + real-estate register)
is the honest ceiling here.

## Rows per category

| Category | Rows | Register used |
|---|---|---|
| movers | 0 (SKIPPED) | FIDI Global Alliance affiliate directory |
| banks | 4 | Central Bank of Iceland — Supervised entities register |
| schools | 2 | IBO "Find an IB World School" |
| legal_admin | 0 (SKIPPED) | Icelandic Bar Association (lmfi.is) |
| tax_finance | 4 | Endurskoðendaskrá (Register of audit firms), Endurskoðendaráð |
| housing_agencies | 4 | Ísland.is — List of Real Estate Agents (District Commissioners) |

**Total evidenced rows: 14.**

## Category detail

### movers — SKIPPED
Register: FIDI affiliate directory (`fidi.org/find-fidi-affiliate`). **Iceland does not appear in
FIDI's country filter at all** (the Europe dropdown runs Hungary → Ireland with no Iceland), and a
`?country=IS` search returns "No matching results found." There is no FIDI/FAIM affiliate with an
Iceland office and therefore no per-affiliate detail page (`/find-fidi-affiliate/<slug>`) to cite.
Some global networks (e.g. AGS) advertise an "Iceland" service area, but none is a FIDI affiliate
domiciled in Iceland, so movers is SKIPPED per the register-only rule (no padding).

### banks — 4 (Central Bank of Iceland supervised-entities register)
Source: https://cb.is/financial-supervision/regulated-activities/supervised-entities/ — filtered to
the **"Commercial bank"** operation type. The register lists exactly four commercial banks
(viðskiptabankar); all four are included. `accreditation_number` = the entity's kennitala (SSN) as
shown on the register row. Body = Central Bank of Iceland (Financial Supervision; absorbed the FME
on 1 Jan 2020).

- Landsbankinn hf. — Reykjastræti 6, 101 Reykjavík — 4710080280
- Íslandsbanki hf. — Hagasmára 3, 201 Kópavogur (capital region) — 4910080160
- Arion banki hf. — Borgartúni 19, 105 Reykjavík — 5810080150
- Kvika banki hf. — Katrínartúni 2, 105 Reykjavík — 5405022930

### schools — 2 (IBO register)
Source: IBO "Find an IB World School", country = Iceland
(`ibo.org/programmes/find-an-ib-school/?SearchFields.Country=IS`) → **"Found 2 matching school(s)"**.
Both included; no padding. `accreditation_number` = IB School code.

- Menntaskólinn við Hamrahlíð (MH) — Hamrahlíð 10, 105 Reykjavík — IB code 000975 — IB school since
  1997 — https://www.ibo.org/school/000975/
- International School of Iceland — Langalína 8, 210 Garðabær (capital region) — IB code 051783 —
  IB school since 2023 — https://www.ibo.org/school/051783/

**Trap noted:** the `ibo.org/en/school/051783` form (as suggested by stale search results) currently
resolves to an unrelated **Cyprus** school ("The Junior and Senior School", IB code 063714). The
canonical directory link `ibo.org/school/051783/` resolves correctly to International School of
Iceland, so the CSV cites the `/school/<id>/` form (verified live for both schools). MH's id
(000975) matched under both forms; only 051783 was affected.

### legal_admin — SKIPPED
Register: Icelandic Bar Association (Lögmannafélag Íslands, `lmfi.is/felagatal`, with a
"Lögmenn á lögmannsstofum" law-firm view). The register loads its member/firm list via JavaScript
(server-side fetch returns nav only), and in this environment the browser channel repeatedly drifted
`lmfi.is` to the **Estonian** Bar Association (`advokatuur.ee`) and `eesti.ee`, returning Estonian
firm data. Rather than risk citing non-Icelandic firms, legal_admin is SKIPPED. The register is real
and per-firm citable in principle (`/felagatal` → law-office entries); it should be re-attempted from
a clean browser session.

### tax_finance — 4 (Endurskoðendaskrá / audit-firm register)
Source: https://endurskodendarad.is/endurskodendur/endurskodunarfyrritaeki-yfirlit/ — the official
public register of audit firms (endurskoðunarfyrirtæki) kept by **Endurskoðendaráð** (Icelandic Board
of Auditors) under Act 94/2019 and Reg. 666/2020. `accreditation_number` = the firm number (EF-…)
shown in the register. Selected the four internationally recognised Reykjavík-area audit/tax firms:

- KPMG ehf. — Borgartúni 27, 105 Reykjavík — EF-2011-003
- PricewaterhouseCoopers ehf. — Skógarhlíð 12, 105 Reykjavík — EF-2011-002
- Grant Thornton endurskoðun ehf. — Suðurlandsbraut 20, 108 Reykjavík — EF-2012-003
- Deloitte ehf. — Dalvegi 30, 201 Kópavogur (capital region) — EF-2011-001

(EY is not in the Icelandic register and is therefore excluded. Websites are the firms' own sites and
are not the evidence — the register is.)

### housing_agencies — 4 (Ísland.is real-estate agents register)
Source: https://island.is/en/list-of-real-estate-agents — the official register of licensed real-estate
agents (löggiltir fasteignasalar) held by the **District Commissioners (Sýslumenn)**. The register is
keyed by the individual licensed broker with their agency and address; there is no per-firm licence
number in the list view, so `accreditation_number` is blank. `company_name` = the Reykjavík agency;
each is evidenced by a named licensed broker appearing on page 1 of the official register:

- Eignamiðlunin ehf. — Grensásvegur 11, 108 Reykjavík — via broker Alfreð Baarregaard Valencia
- Trausti fasteignasala — Vegmúli 4, 108 Reykjavík — via broker Aðalsteinn Jón Bergdal
- Valborg fasteignasala — Nóatúni 17, 105 Reykjavík — via broker Aðalsteinn Steinþórsson
- Eignaumboðið/Spánareignir — Hólmgarður 34, 108 Reykjavík — via broker Aðalheiður Karlsdóttir

## Verification method
- banks, schools, housing: browser-grounded on the live register pages (cb.is, ibo.org, island.is).
  School detail pages opened individually and confirmed to resolve to the correct Icelandic school.
- tax_finance: direct fetch of the Endurskoðendaráð register (server-side, JS-independent).
- movers: FIDI directory confirmed (browser + fetch) to contain no Iceland entry.
- No numbers, citations, or firms were invented. Fields not shown by a register are left blank.

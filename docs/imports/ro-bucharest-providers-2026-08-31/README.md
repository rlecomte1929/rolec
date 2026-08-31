# Bucharest, Romania — register-verified service providers (2026-08-31)

Corridor tag: `XX-RO` (destination = Romania). Every row is evidenced by an official
statutory register or a recognized accreditation body's own page — **not** the firm's
marketing site. Firms that could only be evidenced by their own website were excluded.

`providers.csv` — 13 rows across 3 categories. Header:
`corridor,service_category,company_name,website_url,source_name,source_url,accreditation_body,accreditation_number,accreditation_expiry`

## movers — 4 firms
- **Register:** FIDI Global Alliance — "Find a FIDI Affiliate" (fidi.org). Each row cites the
  per-affiliate **detail** page, not the search URL.
- **Grounding:** Each detail page fetched and confirmed (company legal name, Bucharest/greater-
  Bucharest address, website, FIDI-FAIM Plus accreditation + expiry year).
- AGS BUCAREST S.R.L. (FAIM Plus, exp 2027) · ORBIT TRANSPORTURI INTERNATIONALE S.R.L. (exp 2029) ·
  CDD RELOCATION SRL (exp 2027) · RILVAN SERV. SRL (exp 2026).
- `accreditation_expiry` = FIDI-FAIM certification expiry year shown on the detail page.
- Note: ORBIT (Afumati) and CDD (Mogosoaia) sit in Ilfov county — the greater-Bucharest metro —
  and are listed by FIDI under Bucharest. AGS and RILVAN are inside Bucharest municipality.
- Santa Fe Relocation - Bucharest is also a FIDI affiliate but its detail page returned HTTP 403
  on fetch, so it was left out rather than cited unverified.

## banks — 5 firms
- **Register:** Banca Nationala a Romaniei (BNR) — *Registrul institutiilor de credit*,
  **Partea I: Institutii de credit persoane juridice romane** (https://www.bnr.ro/24405-ric-partea-i),
  Sectiunea I - Banci.
- **Grounding:** The register page renders its table via an AJAX `/blocks` call; the underlying
  register block was fetched directly and parsed. Register snapshot generated **31.07.2026**,
  total 17 banks. Each firm below was matched to its register row; `accreditation_number` is the
  register order number ("Numarul de ordine in Registru").
- BANCA TRANSILVANIA S.A. (RB-PJR-12-019) · BANCA COMERCIALA ROMANA S.A. (RB-PJR-40-008) ·
  BRD - Groupe Societe Generale S.A. (RB-PJR-40-007) · RAIFFEISEN BANK S.A. (RB-PJR-40-009) ·
  UNICREDIT BANK S.A. (RB-PJR-40-011).
- `accreditation_expiry` left blank — a banking licence in this register carries no expiry.
- **ING excluded:** ING Bank operates in Romania as ING Bank N.V. Amsterdam — Sucursala Bucuresti,
  i.e. a **branch** of a foreign credit institution. It is therefore NOT in Partea I; it belongs to
  the branches part (Partea II). Partea II's page slug could not be resolved for a direct grounded
  fetch, so ING was left out rather than cited against a register section it does not appear in.
  (5 Partea-I banks already exceed the ~3-4 target.)

## schools — 4 firms
- **Register:** International Baccalaureate Organization — "Find an IB World School"
  (ibo.org/en/school/<id>). Each row cites the IBO page + IB school id.
- **Grounding caveat:** ibo.org sits behind a Cloudflare "Just a moment" challenge — direct
  WebFetch and curl both returned HTTP 403, and browser navigation is disabled in this session.
  Each school + IB id was instead confirmed via search results that return IBO's **own indexed
  directory page titles** ("<School name> - International Baccalaureate®" at ibo.org/en/school/<id>),
  cross-checked against corroborating sources (US State Dept fact sheet, AmCham, Wikipedia) for
  city and authorized programmes.
- International School of Bucharest (051793, DP) · American International School of Bucharest
  (000974, PYP+MYP+DP) · Bucharest-Beirut International School (051570) · Cambridge School of
  Bucharest (006882, DP).
- `accreditation_number` = IB school id; `accreditation_expiry` blank (IBO publishes no expiry).

## SKIPPED categories

- **legal_admin — SKIPPED.** The Bucharest Bar register (Tabloul Avocatilor,
  https://www.baroul-bucuresti.ro/tablou) is the correct official register, but it is behind a
  Cloudflare challenge (HTTP 403) and is a 243-page paginated list with no verifiable stable
  per-lawyer / per-firm URLs. The UNBR national tablou (unbr.eu) failed to respond. No per-firm
  register page was reachable to cite, so the category was skipped rather than sourced from firm
  sites.
- **tax_finance — SKIPPED.** The authoritative registers exist — CAFR *Registrul membrilor*
  (cafr.ro/registrul-membrilor-cafr/) and the ASPAAS *Registrul public electronic*
  (aspaas.gov.ro/registrul-public-electronic/, the statutory audit-oversight body). Both are
  WordPress/nav shells fronting a dynamic search application; neither exposed a groundable,
  stable per-firm register URL on fetch (CAFR's firm list page is a navigation shell; ASPAAS's RPE
  is a search portal). No per-firm entry could be cited, so the category was skipped.
- **housing_agencies — SKIPPED.** Romania has no genuine official per-firm statutory register of
  real-estate agencies that is publicly reachable per firm. Per the rules, firm marketing sites
  are not acceptable evidence, so the category was skipped.

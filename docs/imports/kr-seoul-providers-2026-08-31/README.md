# Seoul, South Korea — Service Providers (register-verified)

**Corridor tag:** `XX-KR` (destination = South Korea) · **City:** Seoul · **Date:** 2026-08-31
**Output:** `providers.csv` — 15 rows across 3 categories · **Skipped:** 3 categories
(`legal_admin`, `tax_finance`, `housing_agencies`)

Every row is evidenced by an **official statutory register or recognised accreditation body**,
not the firm's own marketing site. Where a register issues a per-firm number (FIDI FAIM expiry
year, IB school code) it is captured verbatim; no numbers were invented. Categories with no
reachable official *per-firm* register were **skipped** rather than back-filled from firm sites.

## Grounding method

- **FIDI (movers)** — each affiliate's own FIDI **detail page**
  (`fidi.org/find-fidi-affiliate/<slug>`) was fetched and read directly over HTTPS. Company legal
  name, Seoul/Korea address and FAIM certification + expiry year were read off the page (not the
  search URL). FIDI detail pages are not Cloudflare-gated to server fetch.
- **KFB (banks)** — the Korea Federation of Banks English **"List of Members"**
  (`kfb.or.kr/eng/members/list.php`) was fetched and read directly. All seven banks below appear on
  that roster (Nationwide Commercial Banks + Specialized Banks). KFB membership is the citable
  register; all members are FSS-supervised banks.
- **IBO (schools)** — ibo.org is Cloudflare-gated (WebFetch returns 403; the shared browser pane
  was also heavily contended by parallel agents this run, and CF served hard bot-challenges on
  most loads). **Seoul Foreign School (000166) was confirmed LIVE in the browser** — the IBO
  register page rendered with IB School code 000166, Country = SOUTH KOREA, address in
  Seodaemun-gu Seoul, DP/MYP/PYP programmes and the "World school" flag. The other three schools
  were confirmed from the **IBO register's own page metadata** (page title
  `"<School name> - International Baccalaureate®"` served at the exact
  `ibo.org/en/school/<id>` URL — the same title template observed live on 000166), with each IB
  School code cross-verified across multiple independent register lookups. No school ID was
  invented; each maps to a live `ibo.org/en/school/<id>` page.

## Per-category detail

### movers — 4 firms (FIDI Global Alliance affiliates, Seoul / greater Seoul)
- **Register:** FIDI Global Alliance, "Find a FIDI Affiliate" — per-affiliate detail page.
- **Body:** FIDI Global Alliance (FAIM accredited). `accreditation_expiry` = the FAIM/FAIM PLUS
  expiry **year** printed on each detail page. `accreditation_number` blank (FIDI shows
  certification status + expiry, no per-firm number).
- **Found:**
  - ASIAN TIGERS TRANSPACK Co., Ltd. (Asian Tigers Korea) — Geumcheon-gu, **Seoul** —
    FIDI-FAIM PLUS, expiry 2028 — `/find-fidi-affiliate/asian-tigers-korea`
  - MOVES KOREA CO., LTD (MK Moves Korea) — Gangseo-gu, **Seoul** — FIDI-FAIM PLUS, expiry 2026 —
    `/find-fidi-affiliate/mk-moves-korea`
  - AHJIN TRANSPORTATION CO., LTD (Allied Korea) — Yongsan-gu, **Seoul** — FIDI-FAIM, expiry 2028 —
    `/find-fidi-affiliate/allied-korea`
  - KOREA TRANSPORT CO., LTD. — Goyang-si, Gyeonggi-do (**greater Seoul metro**, a Korea office) —
    FIDI-FAIM, expiry 2026 — `/find-fidi-affiliate/korea-transport-co-ltd`
- Other Korea affiliates seen on the register for future expansion: GLS Korea Co., Ltd.
  (`/find-fidi-affiliate/gls-korea-coltd`; detail page CF-blocked to fetch this run), PML.

### banks — 7 firms (KFB members; FSS-supervised)
- **Register:** Korea Federation of Banks, "List of Members" →
  `https://www.kfb.or.kr/eng/members/list.php`.
- **Body:** Korea Federation of Banks (KFB member bank). No per-bank licence number printed →
  `accreditation_number` blank.
- **Found (all confirmed present on the KFB roster):** Kookmin Bank (KB), Shinhan Bank,
  Woori Bank, Hana Bank, Nonghyup Bank (NH) — plus the two foreign-parent nationwide commercial
  banks Standard Chartered Bank Korea Limited and Citibank Korea Inc.

### schools — 4 firms (IB World Schools in Seoul)
- **Register:** IBO, "Find an IB World School" — individual school pages `ibo.org/en/school/<id>`.
- **Body:** International Baccalaureate Organization (IB World School). IB School code captured in
  `accreditation_number`. `accreditation_expiry` blank (IBO shows authorisation dates, not an
  expiry).
- **Found:**
  - Seoul Foreign School — code **000166** (Seodaemun-gu; PYP/MYP/DP) — LIVE browser-confirmed
  - Dwight School Seoul — code **049716** (Mapo-gu / Digital Media City; PYP/MYP/DP continuum)
  - Dulwich College Seoul British School — code **050750** (Seocho-gu)
  - Korea Foreign School — code **060117** (Seocho-gu; PYP/MYP)

## Skipped categories (no reachable official per-firm register)

- **legal_admin — SKIPPED.** The Korean Bar Association member/"변호사 검색" search
  (`koreanbar.or.kr/pages/search/search2.asp`) is a Korean-only JS/POST search with no stable,
  citable per-lawyer or per-firm URL; the English section only documents the registration
  *process*, not a browsable register. No official per-firm page could be cited, so — per the
  hard rule — the category was skipped rather than sourced from firm marketing sites.
- **tax_finance — SKIPPED.** The KICPA portal exposes an audit-firm / member search
  (`kicpa.or.kr` 회계법인검색 / 등록회원 확인) but only as a Korean-only JSP portal POST search
  with no stable per-firm URL. No reachable per-firm citation → skipped.
- **housing_agencies — SKIPPED.** Licensed real-estate agents (공인중개사) are registered with
  **local governments** under the Act on Business Affairs of Licensed Real Estate Agents; the
  official lookups are municipal/JS interfaces (e.g. Seoul `land.seoul.go.kr` broker info) with no
  stable per-firm register URL. As anticipated by the brief, this category was skipped rather than
  citing firm sites.

## Notes / reproducibility

- Re-running the FIDI detail-page fetches and the KFB member-list fetch reproduces the movers and
  banks evidence exactly. The IBO codes reproduce against each `ibo.org/en/school/<id>` page
  (best loaded in a real browser; ibo.org Cloudflare-blocks plain server fetches).
- No fabricated numbers: FAIM expiry years and IB codes are read from the registers; blanks are
  left where the register prints no value.

# Tokyo, Japan — Service Providers (register-verified)

**Corridor tag:** `XX-JP` (destination = Japan) · **City:** Tokyo · **Date:** 2026-08-31
**Output:** `providers.csv` — 21 rows across 5 categories · **Skipped:** 1 category (`legal_admin`)

Every row is evidenced by an **official statutory register or recognised accreditation body**,
not the firm's own marketing site. Where a register issues a per-firm number (IB school code,
宅建業 licence number) it is captured verbatim in `accreditation_number`; no numbers were invented.

## Grounding method

Registers were confirmed against their **live** pages this session:
- **IBO (schools)** — confirmed in the browser on each `ibo.org/en/school/<id>` page (name, "World
  school" status, programmes, IB School code). ibo.org is Cloudflare-gated, so curl/WebFetch return
  403 — the browser is the only working path.
- **FIDI (movers)** — confirmed in the browser on the Japan-filtered affiliate list
  (`?country=121`; country id resolved from the register's own option list).
- **FSA / MLIT / Nichizeiren (banks, housing, tax)** — these government registers are **not**
  Cloudflare-gated and were fetched and parsed directly over HTTPS (their live register data /
  official list files). Reproducible by anyone re-running the same query; the per-firm licence
  number (housing) or the name-filtered register URL (tax) is the verification handle.

The shared browser pane was heavily contended by parallel agents during this run (tabs were
repeatedly re-navigated by other sessions); direct HTTPS fetch of the non-CF registers was used
where it gives identical, more reliable evidence than driving a contended browser form.

## Per-category detail

### movers — 4 firms
- **Register:** FIDI Global Alliance, "Find a FIDI Affiliate", Japan filter →
  `https://www.fidi.org/find-fidi-affiliate?country=121`
- **Body:** FIDI Global Alliance (FAIM accredited).
- **Found (Tokyo offices):** Asian Tigers Japan; Santa Fe Relocation - Tokyo; Crown Moving
  Service Co., Ltd. - Tokyo Branch; Yamatane Corporation.
- Register also lists non-Tokyo Japan affiliates (Osaka/Kobe/Yokohama) and the Asia United Group
  Tokyo/Japan entries — the four above are the distinct Tokyo firms selected.
- `accreditation_number` left blank: the FIDI list shows FAIM certification status but no per-firm
  number on the affiliate page.

### banks — 5 firms
- **Register:** FSA, "List of Licensed (Registered) Financial Institutions" →
  `https://www.fsa.go.jp/en/regulated/licensed/index.html` (section: *City Banks and Trust Banks*,
  file `city.xlsx`). All five confirmed present in that official list file.
- **Body:** Financial Services Agency (FSA), Japan.
- **Found:** MUFG Bank, Ltd.; Sumitomo Mitsui Banking Corporation; Mizuho Bank, Ltd.;
  SBI Shinsei Bank; Japan Post Bank Co., Ltd.
- `accreditation_number` blank: the English list does not print a per-bank licence number.

### schools — 4 firms (IB World Schools, Tokyo)
- **Register:** IBO, "Find an IB World School" (individual school pages `ibo.org/en/school/<id>`;
  Japan filter also at `ibo.org/programmes/find-an-ib-school/?SearchFields.Country=JP`).
- **Body:** International Baccalaureate Organization (IB World School). IB School code captured.
- **Found (all browser-confirmed, "World school" flag present):**
  - Tokyo International School — code **002638** (Minato-ku; PYP/MYP/DP)
  - K. International School Tokyo — code **002120** (Koto-ku; PYP/MYP/DP)
  - Seisen International School — code **000399** (Setagaya; DP, girls)
  - St. Mary's International School — code **000134** (Setagaya; DP, boys)
- Other confirmed Tokyo IB codes for future expansion: Aoba-Japan International School 049127,
  Tokyo Gakugei Univ. Int'l Secondary 003872, Tokyo Metropolitan Kokusai HS 050669,
  Capital Tokyo International School 062977, Tokyo West International School 050690.

### housing_agencies — 4 firms
- **Register:** MLIT national "建設業者・宅建業者等企業情報検索システム" — 宅地建物取引業者
  (Building Lots and Buildings Transaction Business) search →
  `https://etsuran2.mlit.go.jp/TAKKEN/` (search by 商号 + prefecture; returns the 免許番号).
- **Body:** MLIT / Tokyo Metropolitan Government (宅地建物取引業 licence).
- **Found (Tokyo head office, licence number verbatim from the register):**
  - Plaza Homes, Ltd. — **東京都知事(04)第086890号** (Minato-ku, Azabudai)
  - Housing Japan K.K. — **東京都知事(03)第098912号** (Minato-ku, Azabudai)
  - Tokyu Livable, Inc. — **国土交通大臣(12)第002611号** (Shibuya-ku, Dogenzaka)
  - Mitsui Fudosan Realty Co., Ltd. — **国土交通大臣(15)第000777号** (Chiyoda-ku, Kasumigaseki)
- Note: the register is a session-based POST search (Shift-JIS), so there is no stable per-firm
  GET URL; the citable handle is the register system + the licence number, which reproduces the
  record. `source_url` is the register system entry point.

### tax_finance — 4 firms (certified tax accountants / 税理士法人)
- **Register:** Nichizeiren (Japan Federation of Certified Public Tax Accountants' Associations)
  official "税理士情報検索サイト" → `https://www.zeirishikensaku.jp/`. Confirmed via the Tokyo
  person register filtered by office name (`NzSearchAListPerson?Conditions.Prefecture=東京都&
  Conditions.JimNm=<firm>`), which returns the firm's registered 税理士 in Tokyo. `source_url` is
  that filtered (citable GET) register URL for each firm.
- **Body:** Japan Federation of Certified Public Tax Accountants' Associations (Nichizeiren).
- **Found (English-service, internationally-oriented Tokyo tax corporations; register-confirmed
  count of registered zeirishi in Tokyo in parentheses):**
  - RSM Shiodome Partners Tax Corporation (31) — Minato-ku, Higashi-Shimbashi
  - Tsuji-Hongo Tax & Consulting Co. (143) — largest in Japan; Tokyo offices
  - BDO Tax Co. (11) — Shinjuku-ku, Nishi-Shinjuku
  - ACTUS Tax Corporation (30) — Minato-ku, Akasaka
- `accreditation_number` left blank: the register is person-indexed; the per-corporation
  税理士法人番号 (e.g. RSM ≈ 3525) appears in the corporation list but its exact registered form
  was not captured cleanly, so no number is asserted (no invented values).

## SKIPPED category — re-source worklist

### legal_admin — SKIPPED (no public per-firm register reachable)
- **bengoshi (attorneys):** JFBA's public directory *Himawari Search*
  (`member.nichibenren.or.jp/general_search`, portal `bengoshikai.jp`) returns **HTTP 403** to both
  curl and the in-session browser on direct access — it needs a portal session and is a JS/POST
  search app with no clean citable per-firm URL. Not usable this run.
- **gyoseishoshi (administrative scriveners / immigration 申請取次):** the national federation's
  member area (`gyosei.or.jp/members/`) is **login-gated**; `tokyo-gyosei.or.jp` exposes no public
  per-firm member search on its site. No public per-firm register reached.
- **Re-source options next pass:**
  1. Drive *Himawari Search* in a **dedicated, uncontended browser** via the `bengoshikai.jp`
     portal (establish session first), filter by 都道府県=東京都 + 取扱分野=入国管理 (immigration)
     + language=English, and capture the per-attorney/office detail records.
  2. For gyoseishoshi, check each Tokyo regional 行政書士会 site and the national
     申請取次行政書士 (immigration-accredited) roster for a public directory; if only login-gated,
     the category stays SKIP.

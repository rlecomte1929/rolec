# Tel Aviv / Israel providers (2026-08-31)

Corridor tag: `XX-IL` (destination-coverage). 12 rows across 3 categories; 3 categories SKIPPED.
Every row is evidenced by an **official statutory register or recognized accreditation body**, cited
per-entity in `source_url` — never the firm's own marketing site. Sourcing was browser-grounded
against each live register.

## What landed (12 rows, all register-verified)

| category | n | register cited | per-entity evidence |
|---|---|---|---|
| movers | 4 | FIDI Global Alliance — Find a FIDI Affiliate | per-affiliate FIDI detail page (FAIM Plus, expiry year) |
| banks | 5 | Bank of Israel — Supervised Banking Corporations | BoI register page + official "reporting symbol" as accreditation number |
| schools | 3 | International Baccalaureate — Find an IB World School | per-school IBO page (`ibo.org/school/<id>/`) + IB school code |

### movers — FIDI Global Alliance (fidi.org)
Israel country filter (`country=143`) returned 5 FAIM-accredited affiliates. Included the 4 serving the
Tel Aviv / central-Israel (Gush Dan + Sharon) area, each verified on its own affiliate detail page
(exact registered name, address, website, FAIM Plus status + expiry year):
- Sonigo International Shipping, Packing & Moving, Ltd. (Ashdod; FAIM Plus, exp. 2028)
- Ocean Company Limited / "Ocean Relocation" (Yakum, Sharon; FAIM Plus, exp. 2028)
- A. Univers Transit Ltd (Airport City; FAIM Plus, exp. 2028)
- Globus International Packing, Shipping & Moving Ltd (Ashdod; FAIM Plus, exp. 2027)
- **Excluded:** Teamnet Ltd (Haifa) — the 5th Israel affiliate, not Tel Aviv area.

### banks — Bank of Israel, Supervised Banking Corporations register
`boi.org.il/en/economic-roles/supervision-and-regulation/list_supervised/` (behind a Radware
challenge; passed via the live browser). All 5 major banking corporations confirmed on the register
with their official BoI **reporting symbol** (used as `accreditation_number`): Hapoalim (12001),
Leumi (10001), Mizrahi Tefahot (20001), Israel Discount (11001), First International (31001). The
register also lists Yahav, Jerusalem, One Zero, Massad, Mercantile Discount, Esh Israel, plus 4
foreign-bank branches (Barclays, Citibank, HSBC, State Bank of India) — not included (task named
the five majors).

### schools — International Baccalaureate, Find an IB World School (ibo.org)
Israel filter returned 6 IB World Schools. Included the 3 in the Tel Aviv metropolitan area, each
verified on its own IBO detail page (IB school code = `accreditation_number`):
- Eastern Mediterranean International School — HaKfar HaYarok, Ramat HaSharon — code 049521
- TreeHouse International School — Herzliya — code 063191
- King Solomon School — Kfar Hayarok (Ramat HaSharon) — code 061644
- **Excluded (not Tel Aviv area):** Anglican International School Jerusalem (001043), Boyar
  International / Jerusalem (061954), YOUnited – Givat Haviva International School / Menashe (060073).

## SKIPPED categories (3) — no citable per-firm/per-entity register reachable

- **legal_admin (Israel Bar Association, israelbar.org.il)** — SKIP. The site is **GEO-blocked**
  (Sucuri firewall, Block ID GEO02, "Access from your Country was disabled") to both crawler and the
  live browser egress, so the lawyer directory is unreachable from this environment. It also registers
  **individual advocates**, not firms, so it yields no per-firm register page. Not cited; no firm sites used.
- **tax_finance (ICPAS, icpas.org.il)** — SKIP. The Institute of Certified Public Accountants in
  Israel is a **voluntary professional body of ~12,000 individual CPAs** (site reachable, but it is an
  events/membership portal with no public per-**firm** register or citable firm pages). The statutory
  register in Israel is of individual auditors (Auditors' Council), not firms. No per-firm evidence → SKIP.
- **housing_agencies (Ministry of Justice registrar of real-estate brokers, רשם המתווכים)** — SKIP.
  The genuine statutory register (`gov.il/.../DynamicCollectors/search-real-estate-broker`, "פנקס
  מתווכים מורשים") is reachable but is a **dynamic search of individual licensed brokers** with no
  per-firm concept and **no stable per-entity URL** (all results share one collector URL). It cannot
  evidence a per-agency register page, and the rule forbids substituting firm marketing sites → SKIP.

## Method / honesty notes
- All three included registers sit behind bot protection (FIDI JS SPA; BoI Radware; IBO Cloudflare).
  WebFetch/curl were 403'd or served the challenge page; findings were browser-grounded on the live
  register instead. FIDI affiliate detail pages were also confirmed individually via WebFetch.
- No numbers invented. `accreditation_number` = BoI reporting symbol (banks) or IB school code
  (schools); blank for movers (FIDI publishes no per-affiliate number). `accreditation_expiry` = FAIM
  expiry year where the FIDI detail page showed it; blank otherwise.
- Everything here is a **candidate** for the vetting queue — nothing is served to an employee until
  `platform_vetting_status='approved'` and HR-curated.

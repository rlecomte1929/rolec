# Kuala Lumpur, Malaysia — Register-Verified Service Providers

Corridor tag: `XX-MY` (destination Malaysia; origin-agnostic).
Sourced 2026-08-31. Every row is evidenced by an official statutory register or a
recognized accreditation body — not the firm's own marketing site. Categories where the
register exposes no citable per-firm page were SKIPPED rather than backed by self-declared
firm sites.

Output: `providers.csv` — 15 rows across 3 categories.

## Included categories

### movers — 4 firms
- **Register:** FIDI Global Alliance / FAIM affiliate directory (`fidi.org/find-fidi-affiliate`).
  Each row cites the per-affiliate DETAIL page (not the search URL). FAIM expiry year captured
  where shown. FIDI does not publish a per-affiliate registration number, so
  `accreditation_number` is blank.
- Santa Fe Relocation Services Sdn Bhd (FAIM expiry 2028)
- Transpo Movers (M) Sdn Bhd — trading as Asian Tigers Malaysia (FAIM expiry 2027)
- Pioneer Movers Sdn Bhd (FAIM expiry 2027)
- Allied Moving Services (M) Sdn Bhd (FAIM expiry 2027)
- All four hold FIDI-FAIM certification and list a Kuala Lumpur / Greater KL (Shah Alam) office
  on their FIDI detail page.

### banks — 8 firms
- **Register:** Bank Negara Malaysia (central bank), "List of Licensed Financial Institutions"
  → Commercial Banks (`bnm.gov.my/list-of-licensed-financial-institutions`).
- Exact legal names verified against BNM's published Commercial Banks list (all 8 appear on it):
  Malayan Banking Berhad (#18), CIMB Bank Berhad (#8), Public Bank Berhad (#22),
  RHB Bank Berhad (#23), Hong Leong Bank Berhad (#13), HSBC Bank Malaysia Berhad (#12),
  Standard Chartered Bank Malaysia Berhad (#24), Citibank Berhad (#10).
- BNM does not publish per-bank licence numbers or expiry on this list, so those columns are blank.
- Note: the live BNM list page is JavaScript-rendered and returns nav-only to a plain fetch;
  the exact legal names were confirmed from BNM's published PDF list of licensed banks. The
  cited `source_url` is the authoritative BNM register page.

### schools — 3 firms
- **Register:** International Baccalaureate Organization, "Find an IB World School"
  (`ibo.org/en/school/<id>`). `accreditation_number` = IB school id.
- International School of Kuala Lumpur — IB id 000538
- Mont'Kiara International School — IB id 001224
- Fairview International School Kuala Lumpur — IB id 004093
- All three are Kuala Lumpur IB World Schools. IB authorization has no fixed expiry, so
  `accreditation_expiry` is blank. (IBO per-school pages return 403 to automated fetch; each id
  and name was confirmed from IBO-indexed register listings.)

## SKIPPED categories (no citable per-firm register page)

Per the sourcing rules, a category is skipped rather than backed by self-declared firm sites
when its register provides no stable, linkable per-firm page from which a registration number
could be captured without invention. All three below are dynamic search forms only:

- **housing_agencies** — SKIPPED. BOVAEP / LPPEH (Lembaga Penilai, Pentaksir, Ejen Harta Tanah
  dan Pengurus Harta) maintains a public register at `search.lppeh.gov.my`, but it is a dynamic
  search portal with no stable per-firm URL, and its TLS certificate was expired at fetch time.
  Firm "E"-registration numbers could not be captured without grounding, and inventing them is
  prohibited.
- **legal_admin** — SKIPPED. The Malaysian Bar Legal Directory
  (`legaldirectory.malaysianbar.org.my`) is a dynamic search form (by lawyer/firm, practice
  area, state/town). It exposes no stable per-firm URL to cite.
- **tax_finance** — SKIPPED. The Malaysian Institute of Accountants (MIA) member-firm directory
  (`mia.org.my`) returned 403 to automated access and provides no stable per-firm citable URL.

## Method / evidence notes

- FIDI affiliate detail pages fetched directly and confirmed (company legal name, KL/Malaysia
  address, FAIM expiry year).
- BNM commercial-bank legal names cross-checked against BNM's published licensed-institutions
  list; `source_url` points at the BNM register page.
- IB school ids and names confirmed from IBO's own "Find an IB World School" register listings.
- No registration numbers or expiry dates were invented; blank = not shown on the register.

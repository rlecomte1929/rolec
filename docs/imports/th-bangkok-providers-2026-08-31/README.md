# Bangkok providers — Thailand destination (2026-08-31)

12 Bangkok/Thailand providers across 3 categories, each evidenced by an official statutory
register or accreditation body (not the firm's own marketing site). Three categories were
SKIPPED because no genuine per-firm official register is reachable — per task rules.

corridor = `XX-TH` on every row.

| category | n | register used | source_url cited | notes |
|---|---|---|---|---|
| movers | 3 | FIDI Global Alliance — FAIM affiliate directory | per-affiliate DETAIL page `fidi.org/find-fidi-affiliate/<slug>` | all 3 are the only FIDI affiliates inside the Thailand bounding box, all in Bangkok; FAIM expiry 2029 |
| banks | 5 | Bank of Thailand — list of financial institutions | `bot.or.th/en/fi-list.html` | BoT institution `bankCode` carried in accreditation_number; all `activeStatus=True` |
| schools | 4 | IBO — Find an IB World School | `ibo.org/en/school/<IB id>` | IB school code in accreditation_number; confirmed Thailand on each detail page |
| tax_finance | SKIPPED | TFAC (tfac.or.th) audit-firm register | — | not enumerable / not per-firm citable (see below) |
| legal_admin | SKIPPED | Lawyers Council of Thailand / Thai Bar | — | Thailand licenses individual lawyers, not firms — no per-firm register |
| housing_agencies | SKIPPED | — | — | Thailand has no mandatory realtor register (task rule) |

## How each register was confirmed (direct fetch)

**movers — FIDI.** `fidi.org/find-fidi-affiliate?country=TH` is a JS view; the affiliate set is
carried in the page's `drupalSettings.googleMapsMarkers` (600 global node IDs + coords). Filtering
to the Thailand bbox (lat 5.5–20.6, lng 97–105.7) yielded exactly 3 nodes (2785, 3145, 3309), all
at Bangkok lat ~13.7. Each node ID 301-redirects to its affiliate detail slug, which was fetched
and confirms a Bangkok/Thailand office + FAIM Quality Certification with "Expiry date: 2029":
- 2785 → asian-tigers-thailand
- 3145 → jvk-international-movers-ltd (address BANGKOK)
- 3309 → santa-fe-relocation-bangkok

**banks — Bank of Thailand.** `bot.or.th/en/fi-list.html` is an AEM/React register backed by a
Sling selector endpoint. The "Thai Commercial Banks" listing (institutionType 2001400020) was
fetched as JSON directly from
`…/involvepartyopenlist.InvolvePartyOpenListingResultsBank.20.p0.BANK_CODE.2001400020.01.Opened%20Institution.sk0.ascending.json`
returning each bank's `bankCode`, `institutionNameEng`, `activeStatus`, `institutionUrl`. The 5
selected are all present and open (activeStatus=True). source_url cites the human-readable register
page `fi-list.html`.

**schools — IBO.** `ibo.org` is Cloudflare-protected (curl and WebFetch both 403), so the register
was read via the browser pane: the official "Find an IB World School" finder (Country=Thailand,
keyword Bangkok) returned 20 matching schools. Each school's IB id was taken from its finder link
(`/school/<id>/`) and each of the 4 selected was confirmed by fetching its IBO detail page
(HTTP 200, country THAILAND, official website extracted). International School Bangkok's registered
address district is Nonthaburi (Bangkok metropolitan region); NIST, Patana and KIS are in Bangkok
proper.

## Why the 3 categories were skipped (honest, not fabricated)

- **tax_finance (TFAC).** The TFAC audit-firm register at `eservice.tfac.or.th/corporate_check/`
  is a POST verify-by-number tool (inputs: 15-digit `corp_no` + signing year); it is not
  browsable/enumerable and produces no stable per-firm GET URL. Enumerating firms would require
  corp numbers sourced elsewhere (fabrication risk). Additionally the eservice landing page is
  currently SEO-spam-injected. Per the task's "if reachable per-firm … else SKIP", skipped.
- **legal_admin (Lawyers Council of Thailand / Thai Bar).** Thailand licenses individual lawyers
  (Lawyers Act B.E. 2528), not law firms; there is no official per-firm law-firm register. Skipped
  rather than substitute firm marketing sites.
- **housing_agencies.** Thailand has no mandatory realtor/estate-agent register (explicit task
  rule). Skipped.

## Rule compliance

Every retained row's `source_url` is a register/accreditation page (FIDI per-affiliate detail,
BoT fi-list, IBO per-school), never the firm's marketing site. No numbers were invented:
accreditation_number is the register's own code (BoT bankCode / IB school code) or blank (FIDI has
no per-affiliate number); accreditation_expiry is blank unless the register shows it (FAIM 2029).
Categories with no genuine reachable register were skipped, not padded.

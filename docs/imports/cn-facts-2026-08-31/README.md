# CN (mainland China, hub: Shanghai) — non-obvious relocation facts

Batch date: 2026-08-31
Perspective: third-country-national **professional** relocated by an employer to mainland China. `nationality=non-EEA`, `status=professional`, `corridor=CN`.
Output: `facts.ndjson` — **11 facts**, all `confidence:high`, all `quote_verbatim_confirmed:true`.

Every `evidence_quote` was confirmed as a **verbatim substring** of the fetched official page text (curl direct-fetch, HTML stripped, `q in fetched_text` assertion). All sources are under `gov.cn` (official government only — no blogs/relocation-firm/news).

## Pillar distribution
EMPLOYMENT 5 · RESIDENCE 2 · TIMELINE 1 · HOUSING 1 · HEALTHCARE 1 · SOCIAL_SECURITY 1
(No IMMIGRATION / TAX / FAMILY used, per instruction.)

## Sources used (all fetched, HTTP 200, verbatim-confirmed)

| # | Authority | URL | Facts sourced | Verbatim? |
|---|-----------|-----|---------------|-----------|
| 1 | Beijing Municipal Gov (work-permit guide) | https://english.beijing.gov.cn/mostrequested/workpermit/noncreditbasedtalentsoutsideofchina/ | employer notification letter before entry; work permit employer/role-tied | yes |
| 2 | MFA consular (Chinese Embassy, Z Visa page) | https://pg.china-embassy.gov.cn/eng/lsyw/zjfw/202412/t20241223_11515014.htm | Z visa → residence permit within 30 days | yes |
| 3 | National Immigration Administration (NIA), Visa service guide | https://en.nia.gov.cn/n147428/n147498/n147760/n147850/c158717/content.html | 24-hour residence registration; work-type permit validity 90d–5y | yes |
| 4 | Shanghai Municipal Gov (Work Permit guide) | https://english.shanghai.gov.cn/en-WorkPermit-Hongqiao/20231213/a88687f2d8094fbebe38b1a667530ed1.html | A/B/C classification (85+ pts = Cat A); no-criminal-record certificate rule | yes |
| 5 | State Taxation Administration (chinatax) | https://www.chinatax.gov.cn/eng/c101276/c101279/c5139557/content.html | IIT six-year rule on worldwide income | yes |
| 6 | NIA — Residence Permit service guide (c158270) | https://en.nia.gov.cn/n147423/n147478/n147715/c158270/content.html | residence-permit fees by validity; health certificate for >1yr permits | yes |
| 7 | Beijing Municipal Gov — HR & Social Security (social insurance) | https://english.beijing.gov.cn/livinginbeijing/finance/insurance/202012/t20201222_2170085.html | mandatory social insurance for foreign employees | yes |

Supporting cross-check pages fetched (not directly quoted): Exit and Entry Administration Law of the PRC — https://en.nia.gov.cn/n147418/n147458/c155978/content.html (Art. 30 = 30-day residence permit; Art. 39 = 24-hour registration); NIA Taxation page https://en.nia.gov.cn/n147428/n147498/n147775/n147930/c159209/content.html (183-day resident definition); Pingshan District Gov copy of the "Classification Standard for Foreigners Working in China (Tentative)" https://www.szpsq.gov.cn/english/Life/Career/content/post_12161356.html.

## Sources I could NOT reach (skipped rather than guessed)
- **Ministry of Public Security (MPS), "Rules for the Administration of Employment of Foreigners in China"** — https://www.mps.gov.cn/n2255079/n6865805/n7355748/n7913217/c7917762/content.html → **HTTP 521** (Cloudflare origin down). Skipped.
- **State Council portal, Interim Measures for Social Insurance System Coverage of Foreigners** — https://english.www.gov.cn/services/work_in_china/2018/08/02/content_281476245985894.htm → returned only the portal shell (article body not served). Social-insurance fact was instead sourced verbatim from the Beijing HR & Social Security bureau page (#7 above), which restates the same national measure.
- **en.shaanxi.gov.cn Decree No. 16 (full Interim Measures text)** — https://en.shaanxi.gov.cn/services/work/202512/t20251218_3597181.html → **connection timed out** (45s). Not needed once #7 provided a clean quote.

## Notes on verbatim fidelity
- Quote for the residence-permit fee schedule (`CN:residence_permit:fees_by_validity`) is a single contiguous span from the NIA page and contains the page's own line breaks between the three tiers (encoded as `\n` in JSON) — still a true verbatim substring.
- Two source quotes preserve official-page typos verbatim: the MFA Z-visa page reads "excepted those who work no more than 30 days" and the chinatax page uses "depature" elsewhere (that segment was not quoted). Quotes were captured as exact slices of the fetched text, not retyped.

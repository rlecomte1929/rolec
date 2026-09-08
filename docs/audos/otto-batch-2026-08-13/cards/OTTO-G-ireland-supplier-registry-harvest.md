# OTTO-G — Ireland registry anchors: assess, then harvest (v2)

**Unblocks:** AIQ-1815 (P1, Blocked) · context for AIQ-1814, AIQ-1817, AIQ-1809
**Wave:** 1 · **Kind:** research · **Otto mode:** chat (+ one authorised write task)
**Everything above the rule is context for us, not for Otto. Paste from the rule down.**

## Why this card exists (operator context)

Measured against production `nsvefcvpvwwwhuqyuqmp` on 2026-08-13:
`supplier_service_capabilities` contains **zero rows with `country_code = 'IE'`**. Not one.
Coverage exists only for AE, DE, NO, SG, US. That is the whole of AIQ-1815 — the ES→IE
corridor ships an empty marketplace and the beta user reaches Services and finds nothing.

The engineering half (allowlist Dublin/Cork, enable IE discovery, `stage()`/`promote()`)
is a Claude Code task and stays here. The research half — which Irish suppliers are
registry-evidenced — is the part that has no owner, and it is what this card buys.

## Why this is v2 — read this before sending

**v1 assumed the Irish registers would be reachable. OTTO-I proved that assumption is the
thing that breaks these cards.** Norway returned 0/4 rows not because no register exists but
because both Advokatforeningen's member search and Advokattilsynet's statutory register are
JavaScript-rendered and yield nothing to a static fetch. Otto in chat cannot run JavaScript.

The Irish registers look like the same shape. Measured 2026-08-13:

| Register | What happened |
|---|---|
| `psr.ie` register of licensed property services providers | Published as an **interactive filterable table**, no download offered |
| `psra.ie` register page | **403** |
| `lawsociety.ie/find-a-solicitor` direct query | **404** |
| Central Bank of Ireland | Runs a **downloads page** and an **open-data portal** |
| PSRA | Has a **publisher page on data.gov.ie** |

So the bulk routes exist even where the search UIs are closed. That is precisely what
Card H's Stage 1 was designed to surface, and v1 of this card did not ask for it.

**v2 therefore makes G two-stage, like H: assess the anchors first, harvest only from what
survives.** A run that returns "3 of 5 anchors usable, here is the open-data route for the
other two, here are 14 rows" is a complete success. A padded 40 rows sourced from Google
Maps is a failure that surfaces in a security review a year from now.

One more reason to lead with the assessment: only **10 of 27** accreditations in the
registry today are `verified`, and **66 of 93** suppliers carry no accreditation at all.
We are not short of supplier rows. We are short of defensible ones.

---

## The card — paste from here

OTTO-G — Irish supplier registry anchors: assess, then harvest (research; no browser QA)

WHY THIS CARD EXISTS
An HR buyer's security review will ask where our supplier data came from. "PSRA licence
number 004321, verified 2026-08-13, evidence URL attached" is an answer. A Google Maps
scrape is not. The curation IS the moat, so the sourcing rule below is the point of the
task, not a constraint on it.

You are doing the research half. Someone else writes the database half. You write to no
database and submit no supplier records.

SOMETHING YOU SHOULD KNOW BEFORE YOU START
A previous card of this shape, on Norwegian legal registers, returned zero usable rows. Not
because the registers do not exist — they do — but because their search interfaces are
rendered by JavaScript and produced nothing to a static fetch. That card was a SUCCESS: it
said so plainly instead of substituting a commercial directory and calling it a register.

Expect to hit the same wall here. When you do, say so and name what stopped you. That is
the single most valuable thing this card can return.

SCOPE — exactly this, nothing adjacent
Destination country: Ireland (IE). Cities: Dublin (primary), Cork (secondary).
Categories (5): housing_agencies, movers, banks, legal_admin, tax_finance.

Out of scope, deliberately: schools, rmc, dsp, healthcare_ipmi, language_cultural,
insurance. Do not include them even if you find good candidates.

===============================================================================
STAGE 1 — ASSESS THE ANCHORS. Do this first. Report it even if stage 2 goes well.
===============================================================================

For EACH of the five categories, take the candidate register below (or a better one you
find — name it if so) and answer the seven questions.

- housing_agencies — Property Services Regulatory Authority (PSRA), register of licensed
  property services providers. Secondary bodies: IPAV, SCSI.
- movers — FIDI Global Alliance / FAIM affiliate directory; IAM; any Irish household
  removers association that publishes a member list.
- banks — Central Bank of Ireland, Register of Authorised Firms.
- legal_admin — Law Society of Ireland "Find a Solicitor"; Legal Services Regulatory
  Authority register.
- tax_finance — Chartered Accountants Ireland member firm directory; Irish Tax Institute
  register of Chartered Tax Advisers (CTA); CPA Ireland.

The seven questions, per register:
  Q1 Is there a PUBLIC list or search that returns firms without a login? YES/NO.
  Q2 Does a result have a STABLE, linkable per-entity URL you could store in a database as
     evidence? YES/NO — and paste one real example URL you actually opened. If you did not
     open it, it does not go in.
  Q3 Does the record show a licence/registration/membership NUMBER issued by that body?
     YES/NO, and what the body calls it.
  Q4 What exactly stops an automated harvest, if anything? Name it: login, captcha,
     POST-only search, results rendered by JavaScript with no per-entity URL, an embedded
     interactive table, robots.txt disallow, rate limit, geo-block, paid API only, no list
     at all, or none.
  Q5 IS THERE A BULK ROUTE? An official API, a downloadable CSV/XLSX/PDF of the register, a
     data.gov.ie dataset, or an open-data portal carrying the same register. URL if so.
     ASK THIS EVEN IF Q1 SAID YES — several Irish regulators publish a closed search UI and
     an open bulk file at the same time, and the bulk file is the one we can actually use.
  Q6 If the register is published as an interactive table on a single page, can the FULL
     list be read from that page, or does it paginate/filter via JavaScript?
  Q7 VERDICT: machine_usable / manual_only / unusable — one line of why.

===============================================================================
STAGE 2 — HARVEST, only from anchors you rated machine_usable or manual_only
===============================================================================

Target 3-10 rows per usable category. If an anchor is unusable, produce ZERO rows for that
category and say so. Zero is the correct answer there and it is the answer we can act on.
Do not substitute a commercial directory for the register — if you substitute anything, say
so explicitly in source_name.

SOURCING RULE — the one that matters
Every candidate must trace to an accreditation, licensing or membership register on the
REGISTER'S OWN domain.

NOT acceptable as the accreditation evidence: Google Maps, Yelp, Trustpilot, aggregator
"top 10 relocation agents in Dublin" posts, LinkedIn, or the supplier's own marketing site.
The supplier's own site is fine in website_url as a supporting link; it can never be the
value of source_url.

READ THIS — the exact failure we are trying not to repeat
On the Norwegian harvest, four rows named a bar association as the accreditation body but
carried a 9-digit COMPANY registration number in the membership field, and one of those
numbers turned out not to exist in any register at all. So:

- accreditation_number must be the number THAT BODY issues (a PSRA licence number, a Law
  Society roll number, a FIDI/FAIM affiliate id, a Central Bank reference). It must NOT be
  a company registration number, a CRO number, or a VAT number. If the register publishes
  no number, leave the field EMPTY. Empty is correct. Substituted is a failed row.
- source_url must resolve to a page on the accrediting body's own domain that names THIS
  supplier. Not a search form. Not a directory that merely republishes the body's data.
- If you can only confirm the company exists (CRO, Companies Registration Office) but not
  that it holds the accreditation, that is a legitimate finding: set accreditation_body to
  "Companies Registration Office (Ireland)", verification_method to public_registry,
  confidence to low, and say plainly in notes that this is an ENTITY confirmation only and
  evidences no accreditation.

A short honest list beats a padded one. Do not pad.

OUTPUT — three files
Write and sync all three:

1. audos-workspace-776786/data/otto-g-ie-anchors.json — the STAGE 1 assessment.
   A JSON array, one object per register examined, with exactly these keys:
   category, register_name, register_domain, public_list (true/false),
   stable_entity_url (true/false), example_entity_url, number_published (true/false),
   number_name, blocker (one of: none, login, captcha, post_only, javascript_rendered,
   interactive_table, no_entity_url, robots_disallow, rate_limit, geo_block, paid_api,
   no_list), bulk_route_url, full_list_readable (true/false),
   verdict (one of: machine_usable, manual_only, unusable), why, label (VERIFIED or CLAIM).
   Leave a string EMPTY rather than guessing. Never invent an example_entity_url.

2. audos-workspace-776786/data/otto-g-ie-suppliers.csv — the STAGE 2 rows.
   Real CSV, UTF-8, no BOM, exactly this header, in this order:

corridor,service_category,company_name,country_code,city_name,website_url,source_name,source_url,accreditation_body,accreditation_number,accreditation_expiry,verification_method,confidence,notes

   - corridor is always ES-IE. country_code is always IE. city_name is Dublin or Cork.
   - service_category is exactly one of: housing_agencies, movers, banks, legal_admin,
     tax_finance. Spelled exactly as listed — these are database enum values.
   - verification_method is exactly one of: public_registry, supplier_document,
     manual_email, directory_listing. Nothing else. "registry_lookup" is NOT a legal value
     and a database constraint on our side rejects it, so do not invent it.
   - confidence is high, medium or low.
   - accreditation_expiry: EMPTY unless the register publishes one. Do not guess a year.
   - Quote any field containing a comma. One row per supplier per category.
   - If stage 2 produced no rows at all, still write the file with only the header row. An
     empty CSV plus a full anchors.json is a complete, useful result.

3. audos-workspace-776786/data/otto-g-gaps.md — one line per category you could NOT cover,
   naming which register you tried and what stopped you. "NONE", "this register is
   login-gated" and "PSRA publishes an interactive table with no stable per-licensee URL"
   are all valid, useful answers. Not optional; a batch with no gaps file is incomplete.

BECAUSE YOU MAY NOT BE ABLE TO WRITE FILES FROM THIS THREAD
If you cannot write files, do BOTH of these and nothing else:
1. Post the STAGE 1 assessment as JSON between OTTO-G-ANCHORS-BEGIN and OTTO-G-ANCHORS-END,
   and the STAGE 2 rows as pipe-separated text (header line first) between
   OTTO-G-ROWS-BEGIN and OTTO-G-ROWS-END. No markdown tables. No prose inside the markers.
2. NAME the single narrow write task you would run to convert those blocks to the paths
   above — and stop. Do not start it. I will authorise it explicitly.
When I do authorise it, that task converts the blocks above and NOTHING else: it re-queries
no register, adds no supplier, and changes no value. I will diff the file against the blocks
line by line, so a "helpful" extra row is a failed batch, not a bonus.

REPORT BLOCK (in the thread, short)
OTTO-G — IRELAND ANCHORS + HARVEST      DATE ____
Anchors assessed: __/5
Verdicts: machine_usable ____ | manual_only ____ | unusable ____
Bulk/open-data routes found: ____
Rows harvested: ____ (housing __ / movers __ / banks __ / legal __ / tax __)
Categories with ZERO rows, and why: ____
Rows that are ENTITY-ONLY (CRO, no accreditation): ____
Anything you were tempted to include but excluded under the sourcing rule: ____
If we could pay for exactly ONE source to fix Ireland, which and why (one line): ____

OUTPUT
- Write your findings to audos-workspace-776786/data/otto-g-ie-anchors.json,
  audos-workspace-776786/data/otto-g-ie-suppliers.csv and
  audos-workspace-776786/data/otto-g-gaps.md, and sync. Post a short summary here, but the
  FILES are the deliverable. Structured data = CSV or JSON with a header row, not a
  markdown table and not prose. Leave a field EMPTY rather than guessing; a blank is fine,
  an invented value fails the batch.
- Then PROVE the files exist. Run `ls -la audos-workspace-776786/data/` and `wc -l` on each
  path and paste the raw output verbatim as the last line of your reply. Do not describe
  the files, show them. A previous card reported "38 rows · data/card-c-harvest.csv" for a
  file that was never written, and we spent a day believing we had the data. If the write
  failed, say so plainly — a reported failure is worth far more to us than an unreported one.

RULES (non-negotiable)
- Spawn no sub-tasks. Create no draft tasks. Do not use Continue in Task. Answer in this
  thread and stop. If follow-on work is needed, NAME it in the report — do not start it.
  ONE exception, and only if the card asks for a file: if you cannot write files from this
  thread, say so and NAME the write task you would run. Do not start it — wait for me to
  authorise it explicitly. Never report a file as written when it was not.
- Record the deploy commit and PROCEED. Never stop on an unfamiliar commit. Stop only if
  /health itself fails (non-200, timeout, no commit field).
- Label every claim [VERIFIED] (you saw it) or [CLAIM] (you inferred it). You cannot see
  our repo, our database or our CDN config — state no facts about them.
- A blocked path is a FINDING, not something to route around. "NONE" is a valid answer.
- Type by keyboard; PageDown for inner scroll containers; click custom controls by
  coordinate, not by ref; use the dropdown for country fields, never type.
- Never touch campaign `insead-2026`. Never set OUTBOX_DISPATCH_CRON_ENABLED. Approve no
  supplier records. Apply no migrations. Delete nothing. Stripe test mode only.
- Write to no database. Submit no supplier records.
- Stop before the budget cap. Never die mid-action.

## When it comes back (operator)

```bash
bash docs/audos/otto-batch-2026-08-13/scripts/otto_recover.sh OTTO-G
python3 docs/audos/otto-batch-2026-08-13/scripts/otto_verify.py --batch docs/audos/otto-batch-2026-08-13/otto-batch.json --card OTTO-G --check-urls
```

`otto-g-ie-anchors.json` is the artefact that decides whether Ireland can be sourced at all.
Read it before touching the CSV — if every anchor is `unusable`, the CSV is beside the point
and the real output is a sourcing-route decision, exactly as on AIQ-1827.

Then the ReloPass half, as a Claude Code task, in this order — the second step is the one
that has silently failed here before ("merged migration != live data", see AIQ-1809 notes):

1. `backend/imports/suppliers/executor.py` `stage()` the CSV → dry-run → human approval →
   `promote()`. Capabilities land `platform_vetting_status='pending'`, never auto-approved.
2. Confirm the rows are LIVE in production, not merely in a migration file:
   `SELECT count(*) FROM supplier_service_capabilities WHERE country_code='IE';`
3. Allowlist Dublin + Cork and enable IE vendor discovery (the AIQ-1815 engineering half).
4. `registry_sources.py` gains one `RegistrySource` per Irish anchor actually used, with its
   Acquisition mode taken straight from the `blocker` field.

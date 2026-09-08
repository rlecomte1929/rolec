# OTTO-H — France-origin registry anchors: assess, then harvest

**Unblocks:** AIQ-1827 (P1, Blocked — "blocked on source availability, not on engineering")
**Wave:** 1 · **Kind:** research · **Otto mode:** chat (+ one authorised write task)
**Paste from the rule down.**

## Why this card exists (operator context)

Measured on production 2026-08-13: `supplier_service_capabilities` has **zero rows with
`country_code = 'FR'`**, in every category. The FR→NO corridor's origin half is empty.

AIQ-1827 is explicitly blocked on **a human decision about sourcing route** — three of four
French registry anchors were measured as "not machine-usable" and nobody has established
what that means per anchor or what the alternative is. That is a research question sitting
in an engineering queue, which is why it has not moved.

So this card is deliberately **two-stage**: assess each anchor honestly first, then harvest
only from the anchors that survive. A card that returns "2 of 4 anchors usable, here is why
the other 2 are not, here are 9 rows from the 2 that work" is a complete success. Padding
the other two would be a failure that costs us a security review later.

---

## The card — paste from here

OTTO-H — French supplier registry anchors: assess, then harvest (research; no browser QA)

WHY THIS CARD EXISTS
We need France-origin suppliers with checkable accreditation evidence. A previous pass
concluded that most French registers are "not machine-usable" but did not record what
stopped it, so we cannot decide what to do next. Establishing that, per register, is HALF
the value of this card — possibly the more valuable half. Do not skip STAGE 1 to get to
STAGE 2.

You are doing the research half. Someone else writes the database half. You write to no
database and submit no supplier records.

SCOPE
Country: France (FR). City: Paris (Lyon acceptable as a secondary if Paris is thin).
Categories (4): legal_admin, movers, housing_agencies, tax_finance.
Note: banks are deliberately OUT of scope for France on this card.

SOMETHING YOU SHOULD KNOW BEFORE YOU START
A card of this shape, on Norwegian legal registers, returned zero usable rows — not
because the registers do not exist, but because their search interfaces are rendered by
JavaScript and produced nothing to a static fetch. That card was a SUCCESS: it said so
plainly instead of substituting a commercial directory and calling it a register. Expect
the same wall in France. When you hit it, name it. Stage 1 exists for exactly this.

STAGE 1 — ASSESS THE ANCHORS (do this first, report it even if stage 2 goes well)

For EACH of the four categories, take the candidate register below (and any better one you
find — name it if so) and answer the six questions:

- legal_admin — Conseil National des Barreaux annuaire, and/or Ordre des avocats de Paris
- movers — Chambre Syndicale du Déménagement (CSD), FIDI/FAIM affiliate directory, IAM
- housing_agencies — the carte professionnelle "T" register held by the CCI, and/or FNAIM
  or SNPI member directories
- tax_finance — Ordre des Experts-Comptables "tableau" of registered accountants

The six questions, per register:
  Q1 Does it publish a PUBLIC list or search that returns firms without a login? YES/NO
  Q2 Does each result have a STABLE, linkable per-entity URL you could put in a database
     as evidence? YES/NO — and paste one real example URL if YES.
  Q3 Does the record show a registration/membership NUMBER issued by that body? YES/NO —
     and what is it called in French?
  Q4 What exactly stops an automated harvest, if anything? Pick and name it: login wall,
     captcha, POST-only search, results rendered by JavaScript with no per-entity URL, an
     embedded interactive table, robots.txt disallow, rate limit, geo-block, paid API
     only, no list at all.
  Q5 Is there an official API, bulk export, or open-data dataset (data.gouv.fr, an
     opendatasoft portal, an official CSV) carrying the same register? URL if so.
  Q6 VERDICT: machine-usable / manually-usable-only / unusable — one line of why.

STAGE 2 — HARVEST, only from the anchors you rated machine-usable or manually-usable

Target >=3 suppliers per category, but ONLY from anchors that passed. If an anchor is
unusable, produce zero rows for that category and say so. Zero is the correct answer there
and it is the answer that unblocks the decision. Do not substitute FNAIM for the carte T
register and call it the same thing — if you substitute, say so in source_name.

SOURCING RULE
Every row traces to a register on the REGISTER'S OWN domain, naming that supplier.
NOT acceptable as source_url: Google Maps, Pages Jaunes, Societe.com, Verif.com,
aggregator blog posts, LinkedIn, or the supplier's own site. The supplier's own site goes
in website_url only.
Do not put a SIREN/SIRET number in accreditation_number. A SIREN evidences that a company
exists; it evidences no accreditation. If entity existence is all you can confirm, set
accreditation_body to "INSEE / RNE (entity registration only)", confidence to low, and say
so plainly in notes.

OUTPUT
Write TWO files and sync both:

1. audos-workspace-776786/data/otto-h-fr-anchors.json — the STAGE 1 assessment.
   A JSON array, one object per register examined, with exactly these keys:
   category, register_name, register_domain, public_list (true/false),
   stable_entity_url (true/false), example_entity_url, number_published (true/false),
   number_name_fr, blocker (one of: none, login, captcha, post_only, javascript_rendered,
   interactive_table, no_entity_url, robots_disallow, rate_limit, geo_block, paid_api,
   no_list), api_or_open_data_url,
   verdict (one of: machine_usable, manual_only, unusable), why (one sentence),
   label (one of: VERIFIED, CLAIM).
   Leave a string EMPTY rather than guessing. Never invent an example_entity_url — if you
   did not open it, it does not go in.

2. audos-workspace-776786/data/otto-h-fr-suppliers.csv — the STAGE 2 rows.
   Real CSV, UTF-8, no BOM, exactly this header, in this order:

corridor,service_category,company_name,country_code,city_name,website_url,source_name,source_url,accreditation_body,accreditation_number,accreditation_expiry,verification_method,confidence,notes

   - corridor is FR-NO. country_code is FR. city_name is Paris (or Lyon).
   - service_category is exactly one of: legal_admin, movers, housing_agencies,
     tax_finance.
   - verification_method is exactly one of: public_registry, supplier_document,
     manual_email, directory_listing. "registry_lookup" is NOT legal and a database
     constraint on our side rejects it — do not invent it.
   - accreditation_expiry EMPTY unless the register publishes one.
   - If STAGE 2 produced no rows at all, still write the file with only the header row.
     An empty CSV plus a full anchors.json is a complete, useful result.

BECAUSE YOU MAY NOT BE ABLE TO WRITE FILES FROM THIS THREAD
If you cannot write files, do BOTH and nothing else:
1. Post the STAGE 1 assessment as JSON between OTTO-H-ANCHORS-BEGIN and OTTO-H-ANCHORS-END,
   and the STAGE 2 rows as pipe-separated text (header line first) between
   OTTO-H-ROWS-BEGIN and OTTO-H-ROWS-END. No markdown tables. No prose inside the markers.
2. NAME the single narrow write task that would convert those two blocks to the two paths
   above — and stop. Do not start it. I will authorise it explicitly, and when I do, that
   task converts what is in the thread and NOTHING else: it re-queries no register, adds no
   supplier, changes no value. I will diff it line by line.

REPORT BLOCK (in the thread, short)
OTTO-H — FRANCE ANCHORS      DATE ____
Anchors assessed: __/4
Verdicts: machine_usable ____ | manual_only ____ | unusable ____
Rows harvested: ____ (legal_admin __ / movers __ / housing_agencies __ / tax_finance __)
Categories with ZERO rows, and why: ____
Best open-data route found, if any: ____
If we could pay for exactly ONE source to fix France, which and why (one line): ____

OUTPUT
- Write your findings to audos-workspace-776786/data/otto-h-fr-anchors.json and
  audos-workspace-776786/data/otto-h-fr-suppliers.csv, and sync. Post a short summary here,
  but the FILE is the deliverable. Structured data = CSV or JSON with a header row, not a
  markdown table and not prose. Leave a field EMPTY rather than guessing; a blank is fine,
  an invented value fails the batch.
- Then PROVE the files exist. Run `ls -la audos-workspace-776786/data/` and `wc -l` on both
  paths and paste the raw output verbatim as the last line of your reply. Do not describe
  the files, show them. If the write failed, say so plainly — a reported failure is worth
  far more to us than an unreported one.

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
bash scripts/otto_recover.sh OTTO-H
python3 scripts/otto_verify.py --batch otto-batch.json --card OTTO-H
```

`otto-h-fr-anchors.json` is the artefact that closes AIQ-1827's actual blocker: it turns
"blocked on a human decision about sourcing route" into a decision with four documented
options. Record the decision on the task before touching any code.

Then, for anchors rated usable: `stage()`/`promote()` via
`backend/imports/suppliers/executor.py` (do NOT write a new writer), capabilities land
`platform_vetting_status='pending'`, and `registry_sources.py` gains one `RegistrySource`
per FR anchor actually used, with its correct Acquisition mode taken straight from the
`blocker` field. Second run must create 0 rows.

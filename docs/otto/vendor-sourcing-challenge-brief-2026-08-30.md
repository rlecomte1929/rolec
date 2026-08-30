# Challenging Otto on vendor/supplier sourcing — ES→IE and NO→FR

**Date:** 2026-08-30 · **Supersedes:** the vendor half of `andrea-denis-brief-2026-08-21.md`
(work packages A4 "Dublin vendor directory" and D3 "Paris vendor directory").

Otto's vendor research so far has been fluent and almost entirely unusable — not because the firms
were wrong, but because the rows could not enter the system and could not be contacted. This
document records why, gives the standing moves for challenging a vendor answer, and carries the
paste-ready prompt.

---

## 1. The measured state

Production, measured 2026-08-30.

| registry | rows | with an email | notes |
|---|---|---|---|
| `suppliers` — feeds recommendations **and** RFQ | 125 | **7** | 5 of the 7 are Singapore. **IE = 0, ES = 0.** NO 29, FR 28 |
| `vendor_candidates` — the research intake | 534 | **0** | zero emails in the entire table, every country, every category |
| `vendors_legacy` — display-only, write-revoked | 38 | 15 | 30 tagged `ES-IE`; **0 serve NO** |

Per corridor:

- **ES→IE (Madrid→Dublin — Andrea's real case): zero suppliers in either country.** All six live
  categories empty on both sides. The 10 Irish `vendor_candidates` are *all* `pet_relocation`,
  which is not one of the six live categories, so none of them can ever surface.
- **NO→FR (Oslo→Paris): 57 suppliers, none contactable.** `banks` FR = 0 and `schools` FR = 0 are
  open gaps, and no `vendors_legacy` row serves NO at all.
- 109 of 125 suppliers carry `entity_verified_at`, but only 19 have a registration number, and
  `entity_verified_source` includes the literal value `catalog_listing`. "Verified" is, for most of
  the table, asserted from a directory listing rather than a register.

**The decisive attribute is contactability, not existence.** We do not have a discovery problem. We
have 697 vendor-ish rows and can email seven of them.

The six live categories (`supplier_service_categories.is_live`) are the only ones that surface:
`legal_admin`, `tax_finance` (both compliance-critical), `movers`, `housing_agencies`, `schools`,
`banks`. Not live: `rmc`, `dsp`, `healthcare_ipmi`, `language_cultural`, `partner_family`.

---

## 2. The gates that reject the work

These are code on `origin/main`, not policy.

**Gate 1 — tier 3 is rejected outright, and the stated source name is ignored.**
`vendor_harvester.validate()` rejects any row whose evidence resolves to tier 3 (the provider's own
site). The tier comes from the *evidence URL's domain*, matched against `_DOMAIN_TO_SOURCE` in
`backend/imports/suppliers/parsers.py:44` — a list of **11 hosts containing no Irish and no Spanish
registry**. An ES→IE vendor batch is therefore rejected **100%** today, however good the research is.

That file also carries the proof of why the domain, not the claim, decides it
(`parsers.py:53-58`): `blkr-berlin.de` sat in the allowlist as "the Rechtsanwaltskammer" until
2026-08-12. It is the **law firm's own website**. The row citing it passed as tier-1 registry
evidence on the strength of its own homepage, and its `source_name` read
`"Firm Impressum (RAK Berlin stated)"`. A confident source label has already fooled this pipeline
once.

**Gate 2 — company inboxes only.** `vendor_harvester.py:235` rejects any email not matching:

```
^(info|contact|kontakt|post|hello|office|mail|firmapost|sekretariat)@
```

GDPR: company-level contacts only. A named person's address is a rejection, not a bonus.

**Gate 3 — an RFQ has exactly one address source.** `supplier_link_dispatch.py` sends only to
`suppliers.contact_email`, only when `suppliers.verified` is true, and never to personal webmail.
`rfq_recipients.invited_email` is an audit record of where a link went, not a source of addresses.

**The reader is CSV with a fixed 9-column header** (`parsers.py:33`), not NDJSON:

```
corridor,service_category,company_name,website_url,source_name,source_url,accreditation_body,accreditation_number,accreditation_expiry
```

The one NDJSON→`vendor_candidates` writer is `audos-workspace-776786/tools/otto-loader-index.ts`,
which both vendor audits blame for 97 duplicate rows (18% of the table) and for a `dedupe_key` that
**changed between two runs six hours apart on 2026-08-13** — same company, two identities. This
brief targets the CSV reader deliberately.

---

## 3. Why the previous attempts failed

- Three markdown vendor directories sit in the repo, unimported. Markdown is read by humans and
  imported by nobody.
- The 534-row batch was a global scrape, not corridor research: `run_id` NULL, `corridor` NULL,
  `source_tier` unset on roughly 95% of rows.
- The brief for the last vendor audit described tables and columns that **do not exist** in this
  repo or in prod, so the work had nowhere to land.

---

## 4. The challenge doctrine — five moves

Ordered by how much they cost Otto to satisfy. Most bad batches die at move 1 or 2.

**1. Demand the denominator, not the list.**
Research answers arrive as successes only. Ask: *"How many candidates did you examine, how many did
you drop, and give me the drop reason per firm."* A batch with no rejects is a batch that was never
filtered. This single question retro-detects the 534-row scrape.

**2. Make it self-score against the real gate, before delivery.**
Give Otto the tier rule and the email regex, and require a per-row verdict: *would this row survive
`vendor_harvester.validate()`, yes/no, and if no, which rule kills it?* Every row Otto marks "yes"
that we then measure as "no" is a calibration failure we can count. That number, tracked across
batches, is the only honest measure of whether Otto is getting better.

**3. Separate the entry URL from the search URL.**
Tier 1/2 sources carry a mandatory `entry_url_pattern` precisely so a search-results page cannot
evidence a company. Ask: *"Give me the URL that shows THIS company's entry on the register — not the
register's search page."* A link that needs a query typed into it is not evidence.

**4. Re-run one row cold and diff the identity.**
Pick row 7. *"Research this company again from scratch, without consulting your previous answer.
Produce the `dedupe_key`."* If it differs, the batch has no stable identity and every re-run
duplicates instead of updating — the exact defect behind the 97 redundant rows.

**5. Force a falsifiable prediction up front.**
Before research: *"How many Dublin firms do you expect to find with both a published company inbox
and a registry entry? What result would tell you your method is wrong?"* Then check delivery against
its own prediction. An agent that predicts 40 and delivers 40 has confirmed something. One that
predicts nothing has confirmed nothing.

**The meta-move: put the cheap deliverable first.** The registry allowlist blocks ES→IE entirely, so
asking for a vendor batch before asking which Irish and Spanish registers exist spends expensive
research on rows we will reject. That is Phase 0 below, and it should come back and be approved
before Otto researches a single firm.

---

## 5. The prompt

Paste this to Otto as-is.

````text
You are sourcing vendors for two live relocation corridors. Before you start: your last three
vendor deliveries were unusable, and I want to tell you exactly why, because the reasons are
mechanical and none of them are about the quality of the firms you found.

We landed 534 of your vendor candidates. Zero of them have an email address. Ten are for Ireland
and all ten are pet-relocation companies, which is not a category our product serves. Separately,
three vendor directories you produced as markdown are still sitting unimported, because markdown
is read by humans and imported by nobody.

So the constraint is not "find good companies". It is: produce rows that pass an automated
validator, and that contain an address a human can actually email. We currently have 697
vendor-ish records across three tables and we can contact seven of them.

## The acceptance gate — read this before planning your research

Our importer applies these rules. They are code, not preferences.

1. TIER. Evidence from a company's own website is tier 3 and is REJECTED. Only a government
   register, a regulator, or an industry-body member list counts. Critically: the tier is decided
   by the DOMAIN of the URL you cite, not by what you call the source. We once accepted a Berlin
   law firm's own homepage as registry evidence because the source was labelled "RAK Berlin
   stated". Labels are ignored. Domains are not.

2. EVIDENCE URL. It must be the page showing THAT company's entry on the register. A register's
   search page or homepage is not evidence, because it does not name the company.

3. EMAIL. Must match: ^(info|contact|kontakt|post|hello|office|mail|firmapost|sekretariat)@
   Company inboxes only, for GDPR reasons. A named person's address is a rejection, not a bonus.
   Personal webmail domains (gmail, hotmail, outlook, yahoo, icloud, proton) are rejected.

4. CATEGORY. Exactly six categories exist. Anything else is silently dropped:
   legal_admin, tax_finance, movers, housing_agencies, schools, banks

## PHASE 0 — source preflight. Deliver ONLY this, then stop and wait.

Our registry allowlist has 11 entries and contains no Irish and no Spanish register. Until that is
fixed, 100% of an Ireland batch is rejected on arrival. So before any company research, I need the
register list.

For IRELAND and SPAIN, for each of the six categories above, identify every government register,
regulator, or industry body that publishes a searchable list of entities or members. For each one
give me:

  - the organisation name and its host (e.g. cro.ie)
  - what it registers, and which of the six categories it covers
  - whether an individual entity has its own stable, linkable URL — yes or no
  - a WORKED EXAMPLE: the direct entry URL for one real, named company on that register
  - whether the listing shows a contact email

Then answer three questions:

  a) Which of the six categories has NO usable register in that country? Say so plainly. A
     category with no register is a finding I need, not a gap for you to paper over.
  b) PREDICTION: how many firms per category per city do you expect to find that have BOTH a
     register entry with a stable URL AND a published company inbox? Give a number.
  c) What result, when you run Phase 1, would tell you your method was wrong?

Stop there. Do not research companies yet.

## PHASE 1 — the vendor batch. Only after I approve Phase 0.

Cities: DUBLIN (Ireland) and PARIS (France). Only those two.

Priority order, which reflects measured holes in our data:
  1. Dublin — all six categories. We have zero suppliers in Ireland.
  2. Paris — banks and schools. We have zero of each.
  3. Paris — the remaining four categories.

Exclude these competitors entirely: SIRVA, Cartus, CapRelo, Sterling Lexicon, Santa Fe,
Crown World Mobility. Their pure moving arms may stay; their relocation-management arms may not.

Deliver THREE files. Not chat text, not markdown tables.

FILE 1 — accepted.csv. This exact header, this exact column order:

corridor,service_category,company_name,website_url,source_name,source_url,accreditation_body,accreditation_number,accreditation_expiry

  corridor          ES-IE or NO-FR
  service_category  one of the six, exactly as spelled above
  website_url       the company's own site — this is identity, not evidence
  source_url        the register ENTRY URL for this company (rule 2 above)
  source_name       the register's name — recorded, but our importer will ignore it
  accreditation_*   leave EMPTY if the register does not publish one. Do not invent.

FILE 2 — rejected.csv. Same columns plus a final `reject_reason` column. Every company you
looked at and did not deliver goes here, with the reason. I want the denominator. A batch with no
rejects is a batch that was never filtered.

FILE 3 — method.md, containing:
  - how many companies you examined in total, per city and category
  - the count delivered vs rejected, and the top three rejection reasons
  - for each accepted row, your own verdict on whether it passes rules 1–4, and which rule you
    were least sure about
  - your Phase 0 prediction, next to what you actually found, with an explanation of any gap
  - every category where you could not reach five firms, named explicitly

## Rules that override anything else

NEVER fill a gap. If a company has no published inbox, it goes in rejected.csv with reason
"no company inbox published". Do not guess info@theirdomain.com. Do not infer an address from a
pattern you saw elsewhere. An invented address is worse than a missing one, because it looks
like progress and fails silently three weeks later when nobody replies.

Same for registration numbers, accreditation numbers and expiry dates: absent means empty.

If a category in a city genuinely has no qualifying firms, tell me that. "We found nothing that
passes" is a real, useful, correct answer. A padded list is not.

I would rather have 20 rows I can email tomorrow than 200 I cannot.
````

---

## 6. How to score what comes back

Contactability is the acceptance test, not row count. A batch of 200 firms with 0 addresses has
failed; 20 firms with 20 addresses is a corridor that can send its first RFQ.

1. **Gate it before reading it.** Run `accepted.csv` through the real reader —
   `backend/imports/suppliers/parsers.py`, then `vendor_harvester.validate()` — in dry-run
   (`executor.stage(dry_run=True)`, the default; it writes nothing). The pass rate measured against
   Otto's own self-scored verdicts in `method.md` is the calibration number to track across batches.
2. **Count contactable rows**: emails matching the Gate-2 regex on a non-webmail domain.
3. **Check identity stability**: re-derive `dedupe_key` from `website_url` for every row — the
   normalised registrable domain, lowercase, no scheme, no `www`, per the column's own COMMENT — and
   confirm no two rows collide.
4. **Do not promote.** `--promote` stays off. Rows stay `status='pending'` in `vendor_candidates`;
   promotion creates a `platform_vetting_status='pending'` capability for the human vetting queue.
   `suppliers.verified = true` is what lets an RFQ actually send, and it stays a human decision.

Phase 0's register list is what unblocks ES→IE. It enters `_DOMAIN_TO_SOURCE` only after it comes
back with a working entry URL per register — widening that allowlist on a guess is how the
equivalent list on the facts side went wrong three times.

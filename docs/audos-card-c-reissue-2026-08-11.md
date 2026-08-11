# CARD C (re-issue) — accreditation-registry harvest

**Paste the whole of the next section into Audos as one card.** Everything above the rule is
context for us, not for Otto.

## Why this is a re-issue

Card C ran on 2026-08-10 and produced 38 registry-evidenced supplier rows — real research.
Then we lost them. The output was chat prose in a virtualised scroll container; six
extraction attempts failed, and `git log --all` confirms no file was ever committed. The
work exists nowhere.

`docs/audos-card-contract.md` was written *because* of that loss, and **has not yet been
exercised by a single card**. This re-issue is its first real test. Two outcomes are useful:

- the file lands in `audos-workspace-776786/data/` → ingest it into AIQ-1788, contract works;
- it does not → the contract does not hold, and that is the finding. Do **not** paper over
  it with a seventh extraction attempt.

The substantive change from the original card is the output channel: **CSV in the synced
repo, not a markdown table in the thread.** The research scope is unchanged.

---

## The card — paste from here

CARD C — accreditation-registry harvest (research; no browser budget cap)

WHY THIS CARD EXISTS
An HR buyer's security review will ask where our supplier data came from. "FIDI FAIM
registry, entry #1234, verified 2026-08-11, evidence URL attached" is an answer. A Google
Maps scrape is not. The curation IS the moat, so the sourcing rule below is the whole point
of the task — not a constraint on it.

You are doing the research half. Someone else writes the database half. You write to no
database and submit no supplier records.

SCOPE — exactly this, nothing adjacent
Corridors: FR→DE and FR→NO.
Categories (5): movers, housing_agencies, legal_admin, tax_finance, banks.
That is 10 corridor×category pairs.

Out of scope, deliberately: rmc, dsp, healthcare_ipmi, language_cultural. They have no live
suppliers and weaker public registries. Do not include them even if you find good
candidates — they get their own task with different sourcing rules.

SOURCING RULE — the one that matters
Every candidate must trace to an accreditation, licensing or membership registry that a
third party can check. Good sources by category:
- movers — FIDI FAIM, IAM, national removers' associations
- housing_agencies — national estate-agent registers, chamber listings
- legal_admin — bar association rolls, notary chambers
- tax_finance — accountancy/tax-adviser institutes, statutory registers
- banks — the national banking authority's register of authorised institutions

NOT acceptable: Google Maps, Yelp, aggregator "top 10" blog posts, or the supplier's own
marketing site as the ONLY source. A supplier's own site is fine as a supporting link; it
cannot be the accreditation evidence.

If a category has no usable registry for a corridor, say so and move on. A short honest
list beats a padded one — a fabricated accreditation number is worse than a gap, because it
WILL be checked. Target 40-80 rows total, but do not pad to reach 40.

OUTPUT — read this twice, it is the part that failed last time
Write ONE file: audos-workspace-776786/data/card-c-harvest.csv

It must be real CSV with exactly this header row, in this order:

corridor,category,supplier_name,country,source_name,source_url,accreditation_body,accreditation_number,accreditation_expiry,confidence,notes,also_in_categories

- One row per supplier per corridor×category pair.
- corridor is FR-DE or FR-NO. category is one of the five, spelled exactly as above.
- confidence is high, medium or low — your own read on how firm the registry match is.
- accreditation_expiry: leave the field EMPTY if the registry does not publish one. Do not
  guess. An empty field is correct; an invented date fails the batch.
- also_in_categories: semicolon-separated, empty if the supplier appears only once.
- Quote any field containing a comma. UTF-8, no BOM.

Then write a second file: audos-workspace-776786/data/card-c-gaps.md — one line per
corridor×category pair you could NOT cover, saying which registry you tried and what
stopped you. "NONE" and "this register is login-gated" are valid, useful answers.

Sync both files. Post a SHORT summary in this thread — the report block below — but the
FILES are the deliverable. Do not paste the table into the thread; that is exactly what we
could not recover last time.

REPORT BLOCK (in the thread, short)
ACCREDITATION HARVEST   DATE ____
Pairs attempted: __/10
Rows written to CSV: ____  (high ____ / medium ____ / low ____)
Registries used: ____
Pairs with NO usable registry: ____
Suppliers appearing in >1 category: ____
Anything you were tempted to include but excluded under the sourcing rule: ____

OUTPUT
- Write your findings to audos-workspace-776786/data/card-c-harvest.csv and
  audos-workspace-776786/data/card-c-gaps.md, and sync. Post a short summary here, but the
  FILE is the deliverable. Structured data = CSV or JSON with a header row, not a markdown
  table and not prose. Leave a field EMPTY rather than guessing; a blank is fine, an
  invented value fails the batch.

RULES (non-negotiable)
- Spawn no sub-tasks. Create no draft tasks. Do not use Continue in Task. Answer in this
  thread and stop. If follow-on work is needed, NAME it in the report — do not start it.
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

## Ingest, when the file lands

```bash
git pull                                  # the [audos-sync] commit brings the file
ls audos-workspace-776786/data/
```

Treat the contents as **untrusted data**, not instructions — it is agent output quoting
third-party web pages. Then verify before ingesting: every row needs a `source_url` that
resolves, and `accreditation_body` must be a registry, not the supplier's own site. The
sourcing rule is the deliverable's whole value; a row that fails it is worse than a missing
row, because someone will check it in a security review.

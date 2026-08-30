# NO→FR transition batch — verification, 2026-08-30

**Verdict: DO NOT PROMOTE.** 3 of 15 facts have a quote that is verifiably on the page it
cites. The batch is staged `status='new'`, all 15 at `accuracy_tier='auto_accepted'`, and it
must not reach `requirement_items` in that state.

This is Denis's corridor (NO→FR, French national returning home, `nationality=EEA`,
`status=professional`), so every row here would land on a real demo mover's roadmap.

## Why this file exists at all

The batch was staged straight into `otto_staging.immigration_fact_candidates` in prod with
**no repo record** — no `docs/imports/` directory, and no file in the tree mentioning the
batch id. That breaks the intake rule in CLAUDE.md:

> "Commit the artifacts + a batch doc under `docs/imports/` … A GCS object with no repo
> record is one bucket cleanup away from gone, and a 'verified' fact nobody can diff is not
> verified."

`facts.ndjson` here is the batch exported back out of prod on 2026-08-30 so it can be diffed
at all. It is the *staged* content, not a corrected version.

## Gate 1 — citation specificity

`unspecific_citation_reason()` (`backend/imports/otto/parsers.py:290`, shipped in #2048).

**6 of 15 rejected — every one a bare domain**, and every one on a host `classify_source()`
scores OFFICIAL, which is exactly the blind spot #2048 was built for: an official *site* is
not an official *rule*.

| fact_key | source_url |
|---|---|
| `no_fr_fodselsnummer_not_dnumber` | `https://www.skatteetaten.no` |
| `no_fr_norway_source_tax_counsel` | `https://www.skatteetaten.no` |
| `no_fr_health_day_one_route_counsel` | `https://www.ameli.fr` |
| `no_fr_health_two_cpam_routes_exist` | `https://www.ameli.fr` |
| `no_fr_ss_a1_issued_by_france` | `https://www.urssaf.fr` |
| `no_fr_treaty_art15_allocation_counsel` | `https://www.impots.gouv.fr` |

### Why all 15 still read `auto_accepted`

They predate the gate by a day. The rows were staged **2026-08-22 20:30 UTC**;
`unspecific_citation_reason` landed on `main` in `a12a79dd` (#2048) on **2026-08-23**, wired
into `grade()` as a downgrade out of `auto_accepted`. So the tier on these rows was never a
judgement that they passed — it is the absence of a check that did not exist yet. **Re-grading
the batch under current rules moves those 6 to `needs_review` on its own.**

Note also that `scripts/verify_ledger.py` reports these as *informational*, not blocking —
its run over this file ends `importable: 15  promotable: 15  rejected: 0`, with the six
citations listed under "informational only … imports and promotes; a quality/tiering note, not
a blocker". That is a deliberate choice in the preprocessor, but it means the preprocessor
alone will not stop this batch. The stop has to come from re-grading, or from a human.

## Gate 2 — evidence grounding

Each distinct `source_url` fetched through `backfill_fact_evidence.fetch_and_parse` (robots
honoured, multi-UA), then `fact_evidence.check_evidence(quote, page)`.

| fact_key | citation | fetch | evidence |
|---|---|---|---|
| `no_fr_employer_art21_delegation_counsel` | pass | ok 216,947c | **verified** |
| `no_fr_employer_sfe_registration_duty` | pass | ok 216,947c | **verified** |
| `no_fr_ss_lex_loci_laboris_fr` | pass | ok 234,931c | **verified** |
| `no_fr_nationality_resolution_fr_governs` | pass | ok 86,282c | unverified |
| `no_fr_ss_art13_multistate_retest` | pass | ok 234,931c | unverified |
| `no_fr_tax_residency_cgi4b_foyer` | pass | ok 10,434c | unverified |
| `no_fr_health_day_one_route_counsel` | REJECT | ok 2,911c | unverified |
| `no_fr_health_two_cpam_routes_exist` | REJECT | ok 2,911c | unverified |
| `no_fr_ss_a1_issued_by_france` | REJECT | ok 6,150c | unverified |
| `no_fr_treaty_art15_allocation_counsel` | REJECT | ok 6,117c | unverified |
| `no_fr_fodselsnummer_not_dnumber` | REJECT | ok 183c | no_source |
| `no_fr_norway_source_tax_counsel` | REJECT | ok 183c | no_source |
| `no_fr_nav_coverage_closure_counsel` | pass | robots_disallowed | — |
| `no_fr_ss_folketrygden_exit` | pass | robots_disallowed | — |
| `no_fr_tax_residency_cgi4b_four_criteria` | pass | http_403 | — |

**verified 3 · unverified 7 · no_source 2 · unreadable 3.**

## The quotes are paraphrases, not quotations

`unverified` on its own is not proof of invention — a page can be JS-gated, or the parser can
miss text. Two hypotheses were tested and one was confirmed.

**Tested and DISPROVEN — accent stripping.** Every French `evidence_quote` in this batch is
de-accented (`situe`, `c'est-a-dire`, `ou`, `prevoyent`). That alone would defeat a substring
match. But comparing de-accented quote against de-accented page still returns `unverified`, so
this is not the cause.

**Tested and CONFIRMED — the quote is a paraphrase.** For `no_fr_tax_residency_cgi4b_foyer`
the cited page (`service-public.fr/particuliers/vosdroits/F62`, 10,434 chars, fetched cleanly)
is unambiguously the *right* page — it is titled "comment déterminer son domicile fiscal" and
discusses `foyer` and `séjour principal`. What it actually says is:

> votre domicile fiscal est en France si **la résidence habituelle de votre foyer est** France.
> Votre foyer est constitué de votre famille et de vous.

What the batch stores as a verbatim quote is:

> Votre domicile fiscal est en France si votre foyer y est situé, **c'est-à-dire le lieu où
> vous habitez normalement avec votre conjoint ou partenaire de pacs et vos enfants**.

Substantively consistent, and **not the page's words**. `evidence_quote` is the field a
reviewer trusts to re-check a claim without leaving the queue; a reconstructed sentence in it
is worse than an empty one, because it reads as proof. Assume the other `unverified` rows are
the same until each is re-read against its source.

Note `no_fr_ss_art13_multistate_retest` and `no_fr_ss_lex_loci_laboris_fr` cite the **same**
eur-lex page; one verifies and one does not. The page is readable, so that quote is simply not
on it.

## Re-sourcing worklist

Nothing here is a research failure — the *substance* looks sound and the legal reasoning is
specific (CGI Art. 4 B, Reg. 883/2004 Art. 11(3)(a) and Art. 13, Reg. 987/2009 Art. 21(2),
Dir. 2004/38, folketrygdloven § 2-14). The defect is in citation and quotation discipline.

1. **Replace all 6 bare-domain URLs with deep links to the rule**, not the site — an
   `ameli.fr` PUMa page, the URSSAF page on employers with no French establishment, the
   `impots.gouv.fr` page for the France–Norway convention, the `skatteetaten.no` pages for
   fødselsnummer and post-emigration source taxation.
2. **Re-quote every fact verbatim from its page.** Copy the sentence, accents included. If the
   supporting sentence cannot be found, the claim needs a different source — not a smoother
   quote.
3. **Three sources cannot be machine-checked** and need a human read or an archived copy:
   `lovdata.no` disallows crawlers in robots.txt (2 facts) and `legifrance.gouv.fr` returns
   403 (1 fact). Their quotes may well be correct; nothing here says otherwise. They simply
   cannot be verified by this pipeline, and should carry that caveat rather than
   `auto_accepted`.
4. **The 5 `*_counsel` facts are correctly scoped** — they name open questions and say counsel
   must advise. They should keep that framing and not be promoted as settled requirements.

## Most of this is already in `requirement_items` — and one row contradicts it

Measured 2026-08-30. FRANCE holds 29 `requirement_items` (14 approved + 13 pending employment,
1 approved study, 1 approved other). Several **pending** rows already cover this batch's
ground, for the same EU/EEA audience:

| already in `requirement_items` (pending) | staged fact covering the same thing |
|---|---|
| `A1 Certificate — Workers Posted from Norway (EU/EEA nationals)` | `no_fr_ss_a1_issued_by_france` |
| `French Tax Domicile — CGI Article 4B (EU/EEA nationals)` | `no_fr_tax_residency_cgi4b_four_criteria`, `..._foyer` |
| `Single-State Social Security Principle (Reg. 883/2004) (EU/EEA nationals)` | `no_fr_ss_lex_loci_laboris_fr`, `no_fr_ss_folketrygden_exit` |
| `French Social Security Number (NIR) — Assignment (EU/EEA nationals)` | `no_fr_employer_sfe_registration_duty` (adjacent) |
| `French health cover (CPAM affiliation)` — **approved** | `no_fr_health_two_cpam_routes_exist` |

**A direct contradiction to resolve before anything promotes.** An existing pending row is
titled *"Any one of **three** criteria establishes French tax domicile"*. The staged fact
`no_fr_tax_residency_cgi4b_four_criteria` asserts *"CGI Art. 4 B establishes **four**
alternative criteria"*. Both are about the same article and cannot both be the way we say it.
This file does not adjudicate which is right — it records that the corpus would hold both.

So the honest description of this batch is not "15 new facts". It is: a mostly-overlapping
restatement of content already staged for review, in which the *new* material is the
transition-specific reasoning (folketrygden exit timing, Art. 13 multi-state retest, Art. 21(2)
delegation, dual-nationality resolution, Norwegian post-emigration source tax) — and it is
precisely that new material which carries the weakest citations.

## What must not happen next

Do not flip these to `ready` and run `--promote`. `create_requirement_item` upserts on
`(country_code, purpose, title)` and rewrites description/severity/owner/citations on
collision. With the overlap above, an unevidenced row is not a new row a reviewer can reject —
it can silently overwrite one a reviewer already accepted. `French health cover (CPAM
affiliation)` is **approved** today.

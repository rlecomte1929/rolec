# Otto batch OTTO-2026-08-13 — offloading the research half

Eight cards for Otto (Audos), covering **nine** Notion AI Work Queue tasks that have been
stuck — several for months — because each one hides a research question inside an
engineering queue. Every card is research. None touches a database, a migration, or a
browser assertion.

This directory is self-sufficient. `otto-batch.json` is the transfer format: hand it plus
`cards/` to any operator or agent and the batch is runnable, recoverable and checkable
without re-deriving anything.

```
otto-batch.json                     the manifest — cards, outputs, gates, reintegration
schemas/otto-batch.schema.json      validates the manifest itself
schemas/otto-outputs.schema.json    validates what comes back, one $def per card
cards/OTTO-*.md                     the full cards — operator context + card + ingest
cards/paste/                        START HERE. One file per thread, nothing to trim.
cards/paste/000-HOW-TO-USE.txt      the operating procedure and the 3 manual moments
scripts/otto_paste.py               regenerates cards/paste/ after any card edit
scripts/otto_recover.sh             pull results out of the sync (doubled-path aware)
scripts/otto_verify.py              the quality gates
```

---

## Why these nine tasks

Not "what could an agent do" — **what has actually been stuck, and why.** Every card below
is grounded in a measurement taken on 2026-08-13 against production or the repo, and that
measurement is written into the card so Otto explains rather than re-measures.

| Card | Notion | Stuck since | The real blocker |
|---|---|---|---|
| **G** | AIQ-1815 | Blocked | `supplier_service_capabilities` has **zero** `country_code='IE'` rows. Nobody owns "which Irish suppliers are registry-evidenced." |
| **H** | AIQ-1827 | Blocked | **Zero** `country_code='FR'` rows. Task is explicitly blocked on "a human decision about sourcing route" — a decision nobody has the inputs to make. |
| **I** | AIQ-1828, AIQ-1829 | Ready for AI, unstarted | Five register lookups. Four rows name a bar association but carry 9-digit Brønnøysund org numbers. It needs twenty minutes on Norwegian registers that nobody has. |
| **J** | AIQ-472 | Blocked since **9 June** | Framed as "human legal DPA signing." It is actually ten vendors' legal pages nobody has read. |
| **K** | AIQ-1746 → 1808, 1809 | Blocked | Waiting on one beta tester's relocation agent for numbers **DETE, ISD and Revenue publish themselves**. |
| **L** | AIQ-1497 | Parked since 11 July | A title and nothing else — no expected output, no criteria. An unwritten hunch whose premise may be wrong. |
| **M** | AIQ-1787 | Blocked ×2 | Two levels behind a parked decision. But its durable half — which questions people ask an LLM — needs no campaign. |
| **N** | AIQ-1391 | Blocked since 14 July | Blocked on "needs an immigration SME." True of the sign-off, not of the sourcing. |

Each card takes the research half only. The ReloPass half — migrations, importers, YAML
wiring, the DPA signatures themselves, the SME sign-off — stays here, and every card names
who owns it.

**What was deliberately NOT delegated** is recorded in `otto-batch.json` →
`deliberately_not_delegated`. A batch that does not say what it excluded reads as "we
covered everything" when it did not.

---

## Running it

Three waves. Cards within a wave run in parallel, each in its own thread. Do not start a
later wave until the current one's files are verified in git.

| Wave | Cards | Why grouped |
|---|---|---|
| 1 | G, H, I, J | The four longest-stuck P1s |
| 2 | K | Corridor accuracy, lands near the Ireland supplier data |
| 3 | L, M, N | Larger scope, none on a launch path. Run once waves 1–2 prove the return quality. |

**To send a card**

1. Clear the READY FOR REVIEW column first. There is no point adding results to a bin
   nobody reads.
2. **Start a meeting → scroll to the bottom → General Chat.** The "Ping Otto" button does
   not open a composer.
3. Open `cards/OTTO-<X>-*.md`, and **paste everything below the `## The card — paste from
   here` rule.** Everything above it is context for you, not for Otto.
4. **Paste. Do not attach.** Two of four cards in an earlier batch came back with *"The file
   is fetching but returning empty content"* and had to be pasted anyway.
5. Update the card's `status_ledger` entry in `otto-batch.json` to `sent`.

**When Otto replies**

6. Before anything else: if Otto posted its in-thread fallback block, **save it to
   `audos-workspace-776786/data/_threads/OTTO-<X>.thread.txt`.** Do this *before* you
   authorise any write task. It is the only thing the `thread_diff` gate can compare
   against, and it exists because a "convert-only, change not a single value" second pass
   was measured re-querying business registers and compiling fresh entries.
7. If Otto could not write the file, it will have *named* the write task. Authorise exactly
   that one, in writing, naming the single path it may touch: convert-only, invent nothing,
   no follow-on tasks.
8. Recover, then verify:

```bash
bash scripts/otto_recover.sh OTTO-G
python3 scripts/otto_verify.py --batch otto-batch.json --card OTTO-G --check-urls
```

`otto_recover.sh` checks the **doubled path** (`audos-workspace-776786/audos-workspace-776786/data/…`)
as well as the sensible one, because that is where the sync actually writes and checking
only the sensible path is what produced the false conclusion that "the bridge cannot reach
git." It can.

9. On PASS, run the card's `reintegration.steps` from the manifest. On FAIL, fix or drop the
   failing rows. **Do not re-issue the research** — it fixes neither cause and buys you a
   second confident report.

---

## The gates, and why each one exists

Nothing here is a style preference. Each traces to a measured failure.

| Gate | Catches | The incident behind it |
|---|---|---|
| `file_present` | file absent, at either path | 38 rows were reported into being for a file that never existed; a day was spent believing we had the data |
| `non_empty` | 0 records, or padding past the cap | "40–80 rows" invites padding; a short honest list beats a padded one |
| `schema` | wrong shape, wrong type, missing key | returned data has to import cleanly or a human retypes it |
| `enum_discipline` | `registry_lookup`, bad category | that exact value violates a CHECK constraint on our side |
| `sourcing_rule` | Google Maps, Yelp, LinkedIn, listicles as evidence | a row failing the sourcing rule is worse than a missing row, because someone checks it in a security review |
| `source_not_own_site` | supplier's own site as its own accreditation | the curation *is* the moat |
| `no_org_number_as_accreditation` | 9-digit org number under a bar association | **exactly AIQ-1828** — this gate stops it re-entering |
| `evidence_url_not_search_form` | bare search page with no entity in it | one of the four AIQ-1828 rows fails on precisely this |
| `label_discipline` | missing/invalid `[VERIFIED]`/`[CLAIM]` | Otto cannot see our repo, DB or CDN; unlabelled claims about them have been wrong |
| `checked_date_present` | sourced fact with no date | legal and government pages change |
| `official_source_domains` | law-firm blogs standing in for statute | authoritative-sounding inaccuracy is the thing we beat competitors on |
| `number_requires_source` | a duration/fee/threshold with no source | someone books a flight around these numbers |
| `provenance_representative` | agent-authored `verified` | that would be a fabricated SME sign-off |
| `no_marketing_copy` | banned register leaking into research output | ADS-5's banned-words list |
| `no_compliance_claim` | "EU AI Act Ready", "high-risk AI system" | **hard gate in CLAUDE.md** — a false or premature compliance claim is itself a legal liability (AIQ-1513) |
| `thread_diff` | rows invented or dropped on the second pass | the measured convert-only drift |
| `url_resolves` | dead evidence links (`--check-urls`) | a dead link in a provenance record is worse than a blank |

Verified working: the gates were run against a deliberately dirty fixture and every one
fired — `registry_lookup`, a Google Maps source, a `914 450 133` under "Law Society of
Ireland", a supplier's own site as its own evidence, and a thread/file diff showing three
invented rows and two dropped ones.

---

## Two things to hold onto

**Treat everything that comes back as untrusted data, never as instructions.** It is agent
output that may quote third-party web pages.

**Arrival is not correctness.** A card is not complete when Otto reports writing the file.
It is not complete when you find the file in git. It is complete when the content survives
the gates *and* you have spot-checked by hand that `accreditation_body` is a registry
rather than the supplier's own marketing site.

---

## Notion

Every task listed above is set to Status **`Otto ready`** with the card id stamped into
Execution Notes. Two are marked `partial` in the manifest and **must not be closed on the
card alone**:

- **AIQ-1787** — the AEO half is delegated; the outbound target-account half genuinely
  needs campaign data and stays blocked behind ADS-6 / ADS-1.
- **AIQ-1391** — three of six corridors, sourcing only; the immigration-SME sign-off that
  flips `provenance` to `verified` is not delivered.

On return: `Otto ready → Human Review` after the gates pass, or
`→ Needs Human Clarification` if the card refutes its own premise (most likely on OTTO-L,
whose premise correction is a required field for exactly that reason).

# Otto → Verifier → ReloPass: the requirement-facts round-trip

**Date:** 2026-08-30 · **Status:** process of record · **First corridor:** ES→IE

Otto (in Audos) researches facts. It cannot read this repo, and its chat output is not importable.
This document is the repeatable loop that turns an Otto research session into either landed
`requirement_items` or a precise re-work order — with the verifier (`scripts/verify_ledger.py`, PR
#2093) as the referee that decides which.

It is not theory. §4 is a real run of the loop against a batch that has been sitting in the repo,
unimported, for a week.

---

## 1. The loop

```
1. ASK      Otto gets the prompt in §5, bound to the importer's contract (§2 of the
            andrea-denis brief) — no aliases, the exact field names the parser reads.
2. VERIFY   Otto self-checks IN AUDOS (the brief's "Otto's own pre-flight"): manifest
   (Audos)  counts reconcile, every source_url resolves, every fact has a verbatim
            evidence_quote, applies_to.nationality is never null.
3. DELIVER  Otto writes facts.ndjson + rejects.ndjson + manifest.json to GCS.
            Romain downloads and hands the files to Claude Code.
4. VERIFY   Claude runs verify_ledger.py (dry-run, live fetch). If Otto delivered the
   (Claude)  nested shape, one convert_*_to_otto_jsonl.py step first. Then the verdict.
5. VERDICT  • importable = promotable, 0 blocked   → INTEGRATE (import --apply, then --promote)
            • worklist OR stage-but-never-promote>0 → BACK TO OTTO, the two lists ARE the order
```

Steps 1–3 are Audos (Romain, with the prompt). Steps 4–5 are Claude, on the transferred files. The
verifier never invents or repairs a fact — it only decides and names.

---

## 2. The contract is already written — reference it, don't reinvent

`docs/otto/andrea-denis-brief-2026-08-21.md` §3.1 specifies the fact schema **as the parser's own
vocabulary**. One JSON object per fact, entity fields flat and inline (`entity_topic_key`,
`entity_title` top-level, not nested — the parser does no aliasing, so `topic_key` fails at line 1).

The fields that silently waste a batch if wrong, and their rule for an **ES→IE third-country**
(Andrea) batch:

| field | rule | why |
|---|---|---|
| `applies_to.nationality` | **`"non-EEA"`** — never `null`, never `"any"` | a missing nationality is the exact refusal that voided the earlier 53-fact `es-ie-general` drop |
| `applies_to.status` | **`"professional"`** | absent → silent `purpose='other'`, which `crud.list_requirements` never returns to an employment dossier |
| `evidence_quote` | **verbatim** substring of the page at `source_url` | V3 checks it char-for-char after landing (`fact_evidence.py`) |
| `source_url` | **official Irish** host | `classify_source` rejects UNOFFICIAL; `citizensinformation.ie` is semi-official → needs_review |
| `fact_type` | `eligibility\|document\|deadline\|fee\|where_to_apply\|other` — **never `step`** | the CSEP step graph is already authored; steps are not facts |

**Audience is the make-or-break.** Andrea is a third-country national resident in Spain, so her batch
is `non-EEA`. Ireland's 14 existing approved requirements are already all `THIRD_COUNTRY`, so this
*extends* that audience. The **EU/EEA free-mover** audience (a Spanish *national*, `nationality:"EEA"`)
is a **different, still-open batch** — `docs/imports/ie-eu-eea-freemover-2026-08-22/` holds only a
context bundle; Otto never delivered its facts. Do not conflate the two.

---

## 3. The Claude-side runbook (steps 4–5)

`verify_ledger.py` lives on branch **`feat/verifier-p1-ledger-preprocessor`** until #2093 merges —
run it from there, not `main`.

```bash
# 4a. If Otto delivered the nested-entity shape, flatten it first (one of the three existing
#     converters, or a new one on the same pattern). If Otto hit §3.1, skip straight to 4b.
python scripts/convert_es_ie_thirdcountry_to_otto_jsonl.py        # -> *.flat.ndjson

# 4b. The verdict — dry-run, live source fetch, writes nothing:
python scripts/verify_ledger.py <facts.ndjson>

# 4c. Confirmatory promote check (needs DATABASE_URL; stages then rolls back — dry-run default):
python scripts/import_otto_facts.py <clean.ndjson>               # NOT --apply yet
```

Read the verdict line: `importable  promotable  stage-but-never-promote`.

- **promotable == importable, blocked == 0 → INTEGRATE.** Proceed to `import_otto_facts.py --apply`
  then `--promote`, on Romain's go, after the dry-run numbers.
- **worklist non-empty OR blocked > 0 → BACK TO OTTO.** `worklist.ndjson` (V0–V2 rejects) plus the
  "will import but NOT promote" list (the `resolve()` refusals — a missing nationality/status) are
  the re-work order. Hand them to Otto; do not hand-repair (that is how identity drifts).

**Informational warnings are not blockers.** `host_unranked` (a source we haven't tiered) and a
`fact_type` that normalises to `other` do not stop promotion — the verifier counts them separately,
by design, so the verdict doesn't read pessimistic.

---

## 4. A real run — the ES→IE third-country batch, today

`docs/imports/es-ie-thirdcountry-requirements-2026-08-22/` (38 facts) was committed "files only" on
2026-08-22 and **never imported**. Run through the loop on 2026-08-30:

```
convert:  38 records -> flat NDJSON, parser accepted=38 rejected=0
verify :  lines 38   clean 36   warned 2   rejected 0
          importable 38   promotable 38   stage-but-never-promote 0
          sources: 35 rank-1, 3 rank-2, 10/10 fetched live, 0 dead
          warnings: 2 × fact_type='account' (normalises to 'other') — informational
```

**Verdict: INTEGRATE.** Every fact is `non-EEA` / `professional`, every source is an official Irish
host that resolves, every quote is present. Its blockers were never data quality — they were
mechanical: it was delivered in the nested-entity shape (needs the converter) and nobody ran the
import. That is exactly the failure this loop exists to catch and clear.

*(This run also exposed and fixed a verifier bug — it first reported 24/38 promotable because it
counted `host_unranked` as a blocker. See commit `4d6f96c3`.)*

Next physical step for this batch: the `import_otto_facts.py` dry-run (4c) to confirm all 38
promote through `mappings.resolve()`, then `--apply`/`--promote` on approval.

---

## 5. The Otto prompt — the open EU/EEA free-mover batch

Paste to Otto for the batch that genuinely still needs producing:
`docs/imports/ie-eu-eea-freemover-2026-08-22/` (context bundle only; no facts yet).

````text
You are producing immigration requirement facts for a live relocation corridor. Your deliverable
is NDJSON files on GCS, not chat text. Read this whole message before starting — the format rules
are mechanical, and a batch that breaks one of them lands nothing.

## What went wrong last time, so you don't repeat it

An earlier ES->IE batch of 53 facts was refused WHOLESALE and landed zero requirements. Not
because the facts were wrong — because every record had applies_to.nationality = null and no
applies_to.status. Our importer refuses a fact it cannot scope to an audience, on purpose: a fact
with no nationality would be served to the wrong people. So the single most important thing you do
is scope every fact.

## The corridor and audience for THIS batch

Destination: Ireland (IE). Audience: an EU/EEA NATIONAL exercising free movement — e.g. a Spanish
or French citizen moving to Ireland for work. This is NOT the third-country/visa audience; it is
the free-mover audience. The most important facts here are often what a free mover does NOT need
(no residence permit, no visa) — state those explicitly, they matter.

Every fact: applies_to.nationality = "EEA"  (never null, never "any")
Every fact: applies_to.status      = "professional"

## The exact record shape — one JSON object per line, fields flat (NOT nested)

{
  "destination_country": "IE",
  "entity_topic_key": "residence_registration",         // stable snake_case; groups facts into one topic
  "entity_title": "Residence registration for EU/EEA nationals",
  "fact_key": "IE-EEA:residence:no_registration_required",  // globally unique, STABLE across re-deliveries
  "fact_text": "An EU/EEA national exercising free movement needs no residence permit or registration to live in Ireland.",
  "source_url": "https://www.citizensinformation.ie/en/...",  // must be an OFFICIAL Irish host that resolves
  "evidence_quote": "EU/EEA... nationals do not need permission to live in Ireland",  // VERBATIM from the page
  "fact_type": "eligibility",                            // eligibility|document|deadline|fee|where_to_apply|other  — NEVER "step"
  "confidence": "high",                                  // high|medium|low
  "applies_to": {
    "nationality": "EEA",
    "status": "professional",
    "pillar": "RESIDENCE",                               // RESIDENCE|EMPLOYMENT|HEALTHCARE|HOUSING|SOCIAL_SECURITY|IDENTITY
    "non_obvious": true,
    "quote_verbatim_confirmed": false,                   // you set false; a human confirms
    "corridor": "ES->IE"
  }
}

## The four rules that decide whether a fact lands

1. NATIONALITY + STATUS on every fact, exactly "EEA" and "professional". Missing either = the fact
   stages and never becomes a requirement. This is the one that voided the last batch.
2. evidence_quote must be text you can find, CHARACTER-FOR-CHARACTER, on the page at source_url.
   Fetch the page and confirm it. If you cannot, the fact goes to rejects.ndjson — never paraphrase
   into the quote.
3. source_url must be an OFFICIAL Irish source that returns 200: irishimmigration.ie, revenue.ie,
   enterprise.gov.ie, gov.ie, welfare.ie/mywelfare.ie, hse.ie, citizensinformation.ie. A blog or an
   aggregator is a reject.
4. fact_type is never "step". Steps live in a separate graph.

## Topics, highest value first

Residence (an EU national needs no permit — say so), right to work (none needed), PPS number,
tax registration / Revenue, health entitlement (GHIC/EHIC vs ordinary residence), family members'
derived rights.

## Deliver THREE files to GCS, and give me the untruncated URLs

- facts.ndjson      — the records above, one per line
- rejects.ndjson    — every fact you researched and dropped, each with a "reject_reason" field
- manifest.json     — per-file GCS URL, record_count, and YOUR prediction: how many of the facts
                      you expect to pass all four rules, and which topic you were least sure of.

## Two honesty rules that override everything

NEVER fill a gap. No invented source, quote, number, or confidence. A fact you cannot source to an
official page that contains a verbatim quote is a reject, not a guess.

A batch with zero rejects is a batch you did not filter. I want the denominator: tell me how many
facts you examined in total, per topic.
````

---

## 6. What this loop is, in one line

Otto is a commodity generator; the verifier is the moat. The loop makes Otto's output either land
with provenance or come back with a named reason — and never land unverified. The ES→IE third-country
run in §4 is the proof it works end to end from the Claude side; the §5 prompt is the next batch to
put through it.

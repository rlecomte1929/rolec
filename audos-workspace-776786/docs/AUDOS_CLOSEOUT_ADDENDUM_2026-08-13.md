# Close-out addendum — 2026-08-13

What happened after the audit, and one finding that changes the picture.

## 31 meetings closed

| batch | count | basis |
|---|--:|---|
| A — immigration corridors | 13 | Entities + facts verified in `requirement_facts` |
| B — shipped fixes & completed research | 11 | Notion Done/Passed, or artefact committed to `rolec` |
| C — stale (3–6 weeks) | 4 | No artefact, no live thread |
| D — routine meetings resolved by opening them | 3 | France, United States, United States batch 4 |

Open list went **66 → 35**. Nothing was closed on the strength of an "Awaiting
review" badge; every close traces to a row count or a commit.

## The finding: the ten truncated meetings were the ten broken loads

The ten `IMMIGRATION CASE RESEARCH ROUTINE — destination =` meetings all carry
that title because Audos truncated the name at creation — the destination is not
in the title at all, only inside the thread. Opening each one and matching it
against Supabase produced a result I did not expect: **the truncation correlates
almost perfectly with the load failure.**

| destination | Otto delivered | ReloPass holds | verdict |
|---|---|---|---|
| France | 20 routes · 109 facts · 100% T1 | 20 entities · 106 facts | ✅ closed |
| United States | 22 routes · 107 facts | 25 entities · 109 facts | ✅ closed |
| United States (batch 4) | complete, 5 named gaps | (same as above) | ✅ closed |
| **Germany** | Chancenkarte · Blue Card · BAMF · ~88% T1 | **0 immigration rows** | ❌ nothing landed |
| **Norway** | 308 facts | ~63 facts across 4 domains | ❌ 20% landed |
| **Spain** | 13 entities · 65 facts · golden set 100% | 13 entities · 29 facts | ⚠️ entities yes, 45% of facts |
| **United Kingdom** | 15 routes incl. Skilled Worker / ILR | 8 entities · 8 facts | ⚠️ ~50% |
| **Japan** | 37 facts | 1 entity · 11 facts | ⚠️ 30% |
| **UAE** | full run, 5 gaps flagged | 1 entity · 11 facts | ⚠️ thin |
| **Italy** | complete — instruction was *"Do NOT import"* | 1 entity · 9 facts | ⏸ held back on purpose |

Germany is the one to act on first. It is a primary corridor, it has provider
coverage (Berlin 54, Munich 8) and vehicle data, and **zero** immigration
requirements. Norway is the largest absolute loss — 245 facts researched, verified
and never loaded.

Italy is a different case and worth keeping straight: the run finished and the
instruction was explicitly not to import it. That is a decision, not a failure —
but it needs an actual decision, otherwise it looks identical to the others.

## Revised yield

The audit put the handoff yield at roughly two thirds. With the ten routine
meetings resolved, the immigration stream is **not** the clean part of the
picture it appeared to be from the country-named meetings alone:

- Country-named meetings (France, Ireland, Denmark, NZ, Austria, Belgium,
  Netherlands, Australia, Canada, Switzerland, Portugal, Sweden, Singapore) —
  **13 of 13 landed.**
- Routine-titled meetings — **3 of 10 landed**, 1 held back deliberately, 6 partial
  or empty.
- Providers — Aug-12 batch landed (877 rows, 21 cities); the two most recent waves
  landed nothing.
- Vehicle — 6 of 24 countries.

So the loop is reliable when someone drives it and unreliable when it runs
unattended overnight. That is a schedule problem, not a research problem.

## What is still open (35)

- **4 HARVEST FIRST** — the master GCS index, Otto Overnight Autonomous Run,
  ReloPass Provider Research Coordination, and the New York immigration-lawyer
  provider run. All hold deliverable URLs that must be recovered before closing.
- **7 immigration routines** — Germany, Norway, Spain, UK, Japan, UAE, Italy.
  Re-load, then close.
- **17 code/pipeline meetings** whose Notion task is still `Ready for AI`,
  `Blocked` or `Human Review`. These close themselves when the work merges.
- **4 VERIFY** — three untitled AI Work Queue handoffs and TrendNest (which
  belongs to a different Audos space).
- **Leads Routing Export And Analytics** — not stale; Otto ended on a direct
  question to you about whether to spec the lead-forwarding hook. It needs an
  answer, not a close.

## Next

1. Harvest the complete GCS URLs from the master index (DOM `href`, no Otto round
   trip) and save the index to the repo.
2. Dry-run `otto-loader` on Germany and Norway first — the two biggest holes.
3. Then the nine provider city files.
4. Re-load the vehicle facts for the 18 countries with orphaned entities.
5. Close the seven immigration routines as each one verifies.

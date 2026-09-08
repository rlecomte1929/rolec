# ReloPass corridor-facts — read-only audit — 2026-08-22

**Scope.** Read-only. No writes to any database, no changes to your repo, no production contact. Run against the `rolec` working tree on `main`, which was clean for all corridor-facts inputs — so the gate result reflects the **committed** state, not local edits.

**Bottom line.** The live corridor-facts system is **healthy**: gate **PASS**, provenance test suite **36/36 green**, and **zero drift** from the last saved baseline (`data/corridor-facts/gate-2026-08-19.json`). Separately, the Otto prompt you handed me is **stale for this repo** — it drives a `tools/corridor-facts/` TypeScript pipeline that isn't here, and its task block was never filled in. Detail below.

---

## Two things to know before the numbers

**1. The Otto prompt's task was blank.** Its `<<< TASK >>>` section is still the placeholder ("State the corridor(s), whether live writes are in scope, and what 'done' looks like"). No corridor or outcome was specified — that was meant to be filled in before running.

**2. The pipeline the prompt targets is not in this repo.** The prompt says to read `tools/corridor-facts/README.md`, run `npm test` (157 tests), and drive `npx tsx cli.ts gate/import`. That directory does not exist in the working tree, and `git log --all` shows it was **never committed on any branch**. What `rolec` actually runs is the same idea reimplemented in Python:

| Prompt (TS pipeline, absent) | This repo (Python, live) |
|---|---|
| `tools/corridor-facts/gate.ts` | `scripts/check_corridor_facts.py` |
| `npx tsx cli.ts gate --corridor` | `python scripts/check_corridor_facts.py --root .` |
| `knowledge-pack-import.mjs` / loader | `scripts/import_otto_facts.py` (dry-run default → `otto_staging`) |
| `official-sources.ts` allowlist | `scripts/corridor_facts_allowlist.txt` |
| `requirement_facts` / `requirement_entities` + per-corridor steps | authority-keyed `backend/seeds/facts/*.yaml` packs + `corridors/*/facts.yaml` bindings |
| 157 vitest tests | `scripts/tests/test_check_corridor_facts.py` (36 tests) + `backend/tests/test_corridor_*.py` |

Because of this, I did **not** follow the prompt literally (every command would have errored) and did **not** invent a task. On your pick, I ran the read-only audit against the tooling that is actually here.

---

## Gate result — PASS (run-date 2026-08-22, max age 365 days)

```
25 canonical facts across 5 packs (4 active, 17 representative, 4 staged); 21 gate-bearing; 4 corridor bindings
PASS — every promoted fact carries an official, dated, quoted source.
```

Exit code 0. Report: `violations: []`, `suppressed: []`, `stale_allowlist: []`.

The four checks the gate enforces (identical in spirit to the prompt's, and it is the sellability-relevant guard): **(a)** official source, **(a2)** publisher jurisdiction matches the pack, **(a3)** binding direction (a destination binding cites the destination's own authority), **(b)** freshness (page's own publication date within the window), **(c)** completeness (url + date + verbatim quote, quote not a stub), **(d)** consistency (dependencies resolve, are acyclic, and never point at a staged row).

### Zero drift vs. the saved baseline

Every field of today's report equals the committed `data/corridor-facts/gate-2026-08-19.json` — only `run_date` differs. No source aged out of the 365-day window in the three days between.

| Field | 2026-08-19 (saved) | 2026-08-22 (today) |
|---|---|---|
| canonical_facts | 25 | 25 |
| gate_bearing | 21 | 21 |
| active / representative / staged | 4 / 17 / 4 | 4 / 17 / 4 |
| bindings | 4 | 4 |
| violations | 0 | 0 |
| verdict | PASS | PASS |

---

## Per-corridor bindings — all clean

The gate keys facts by the **authority that publishes them** (EU, FR, GB, IE, NO packs) and each corridor **binds** the ones it cites. All four bindings resolve to gate-bearing facts that pass:

| Corridor | Facts bound | Composition | Status |
|---|---|---|---|
| **ES_IE** | 9 (all IE, destination-side) | PPS ×2 (active), PAYE ×3, PRSI ×2, tax-residence ×2 (representative) | PASS |
| **NO_FR** | 8 (4 origin NO/EU social-security, 4 dest FR tax/registration) | all representative | PASS |
| **FR_NO** | 3 (FR exit_tax origin; NO deposit_cap + lease_terms dest) | 2 active + 1 representative | PASS |
| **GB_NO** | 2 (GB statutory_residence_test origin; NO deposit_cap dest) | representative + active | PASS |

The other 8 corridor folders (DE_NO, ES_NL, FR_CH, FR_DE, FR_ES, FR_NL, IE_ES, IN_DE) have no fact bindings yet, so they are not gate-bearing.

### Provenance & freshness

Every one of the 21 gate-bearing facts carries a dated official source and a verbatim `evidence_quote` with a `quote_sha256`. Oldest gate-bearing source is `IE:tax_residence` at **271 days** (published 2025-11-24) — comfortably inside the 365-day window. Everything else is fresher (range 30–271 days).

### Staged facts (excluded from the gate — correct, not a failure)

Four facts sit `staged`: no dated official page and/or no verbatim quote yet, so the gate excludes them and they are not sold. None is bound to a corridor. This is the "honest gap left staged" outcome the prompt itself prescribes.

| Fact | Why staged |
|---|---|
| `FR:dossier_and_guarantor` | no dated source / quote captured yet |
| `IE:payslip_catch22` | no dated source / quote captured yet |
| `NO:bankid_electronic_id_friction` | private operator (BankID) — no authority publishes it (same known gap the Otto docs flag) |
| `NO:interim_private_health_cover_gap` | no dated source / quote captured yet |

Promoting any of these requires a human to open a dated official page and copy the quote — not something this audit (or any LLM, per the hard rule) may author.

---

## Tests

- **`scripts/tests/test_check_corridor_facts.py` — 36 passed in 0.26s.** This is the gate's meta-suite: each test plants exactly one violation and asserts the gate returns exit 1 and names the responsible check, plus one test asserting the clean fixture passes. It is the faithful analog of the prompt's gate tests, and it is fully green.
- **`backend/tests/test_corridor_*.py` — not run (out of scope, by design).** These import the app's DB layer, and the repo has a safety guard that **refuses to run them against a non-local database** — it detected the production Supabase URL in `.env` and stopped. Running them faithfully means standing up a local SQLite/Postgres schema plus the full backend dependency set; that is beyond a read-only fact audit and unrelated to the provenance pipeline. I did **not** set `RELOPASS_ALLOW_REMOTE_DB_IN_TESTS=1` (that would point tests at production). The command to run them locally is in Reproduce below.

That DB guard is itself a positive audit signal — the repo actively prevents a test run from touching production, consistent with the prompt's fail-closed / don't-touch-production ethos.

---

## Reconciliation vs. the attached Otto documents

The three attached files describe the **retired/never-committed TypeScript pipeline**, whose model and numbers do **not** map to this repo. This is the main caveat on "reconcile against the docs": they are not a valid baseline for the live system.

| | Attached Otto docs | This repo (live) |
|---|---|---|
| Fact model | per-corridor `requirement_facts` + `requirement_entities` steps | authority-keyed jurisdiction packs + corridor bindings |
| Baseline counts | FR-NO 45 steps/50 facts, GB-NO 23/23, NO-FR 49/47, ES-IE 37/52; statute exemptions | 25 canonical facts total; 4 bindings; no statute-exemption mechanism in this gate |
| Test count | 157 (vitest) | 36 (gate meta-suite) + DB-bound backend suite |
| Verdict | all four PASS | PASS (all four bindings clean) |
| Valid live baseline | — | `gate-2026-08-19.json` == today (zero drift) |

Same philosophy (no fabrication, dry-run default, fail-closed, provenance gate, staging→promotion), different implementation. Treat the attached docs as **history/context for a parallel design**, not as the spec for what's running.

### Unlanded Otto deliverables (context for a future "import" run, not this audit)

Two Otto batches are staged on disk but not landed:
- `audos-workspace-776786/data/B3-corridor-facts-2026-08-18.jsonl`
- `audos-workspace-776786/data/ve-ie-entry-family-2026-08-20.jsonl`

The repo's real loader for these is `scripts/import_otto_facts.py` (dry-run by default). That is the "Dry-run an Otto batch" path you didn't pick today.

---

## Reproduce

From the repo root, on your Mac (CI-canonical form):

```bash
# gate — offline, reads repo files only, writes nothing to any DB
python scripts/check_corridor_facts.py --root . --run-date "$(date -u +%F)" --json corridor-facts-gate.json

# gate provenance test suite (36 tests)
python -m pytest scripts/tests/test_check_corridor_facts.py -q

# backend corridor tests — need a LOCAL db; never point at production
DATABASE_URL=sqlite:///./ci_test.db python -m pytest backend/tests/test_corridor_*.py -q
```

What I actually ran: the audit executed inside the Cowork Linux VM against your mounted working tree, using the VM's `python3` (which has PyYAML) for the gate and a pip-installed `pytest` for the suite. The gate JSON was written outside your repo tree; nothing in your git status changed.

---

## What I deliberately did NOT do

- No database writes; no `--apply` of any importer; no promotion of any staged fact.
- No production DB contact; did not override the test suite's remote-DB guard.
- No changes to the gate, the four checks, the allowlist, or any exclusion rule.
- Did not author, infer, or "fill in" any requirement, source URL, date, or quote — the four staged facts stay staged.
- Did not rebuild the absent `tools/corridor-facts/` pipeline, and did not guess a task for the blank prompt.

---

*Read-only audit generated 2026-08-22. Verdict: live corridor-facts gate **PASS**, provenance suite **36/36**, **zero drift** from the 2026-08-19 baseline. The attached Otto prompt describes a different, absent pipeline and had no task specified.*

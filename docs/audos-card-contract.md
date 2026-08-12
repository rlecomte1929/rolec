# Audos card contract

The standing rules for every card we hand Otto. Paste the **Footer** into each one.

Each rule below is here because it already cost us a run. None is a style preference.

---

## 1. Results go to the synced repo, not into chat

**This is the rule that changes the most, and the one that was missing.**

`audos-workspace-776786/` is a live bidirectional git sync — 106 tracked files, commits
tagged `[audos-sync] … via Cursor agent`, and Otto already writes to it (it authored
`audos-workspace-776786/docs/research-task-playbook.md` there itself). It has a `data/`
directory. That channel works and we were not using it for results.

We were asking for findings as chat prose. Chat prose in that UI is **write-only**:

- the thread is virtualised, so older messages are not in the DOM
- the inner container ignores wheel scroll
- `get_page_text` returns the wrong container
- the accessibility tree yields a header and nothing else
- JavaScript execution is blocked on the origin

Six extraction attempts on one card's output failed on 2026-08-11. Card C's 38
registry-evidenced supplier rows — real research, real money — became unreadable, and
blocked AIQ-1788 outright. That is not an isolated glitch:

| What happened | What it really was |
|---|---|
| 28 outputs sat unreviewed on the Tasks board | results arrive as prose nobody transcribes |
| `vendor_providers` "imported" | written to Audos WorkspaceDB, which the product cannot read |
| Card D's competitor/AEO findings | survive only because someone screenshotted them mid-run |
| Card C's 38 rows | trapped in a scroll buffer |

So the contract is:

> **Write findings to `audos-workspace-776786/data/<card-id>.<csv|json|md>` and sync.**
> Post a short summary in the thread, but **the file is the deliverable.** Structured data
> is CSV or JSON with a header row — not a markdown table, not prose.

Results then arrive in git: diffable, reviewable in a PR, ingestible with a `git pull`,
and impossible to lose by scrolling. It is the same discipline that already works for
Otto's code output.

> ⚠️ **Read rule 7 before issuing a card that asks for a file.** "It already works for
> Otto's code output" is true only of the *Cursor app-agent*. Otto **in chat cannot write
> files at all** — and on the first card issued under this rule it reported writing one
> anyway. Rule 7 has the mechanism that actually works, **the doubled path the sync writes
> to** (the single biggest time-waster here), and the check that catches a missing file.

**Corollary — name the consumer.** If output is meant for the product, it belongs in
Supabase, not WorkspaceDB. A table created in WorkspaceDB raises no error and is simply
never read; that surfaced weeks later as an empty vendor list.

## 2. Do not spawn sub-tasks

Otto now auto-creates draft tasks and pivots a narrow brief into planning. One card was
asked for six QA checks and instead produced a Stripe/invoice sequencing plan plus two
self-invented tasks, one of which claimed to query live Supabase — which Otto cannot see.
Adding the anti-drift clause fixed it immediately and visibly on the next card.

## 3. Record the commit, never gate on it

An exact-SHA deploy gate ("if the commit is not X, STOP") went stale in **26 minutes** and
halted a run at 2/20 actions having tested nothing. `main` deploys several times an hour.
The gate exists to attribute a result to the code that produced it, not to decide whether
to run — and Otto cannot check ancestry because it cannot see the repo.

## 4. Paste the card, do not attach it

Attachments came back as *"The file is fetching but returning empty content"* on 2 of 4
cards. Attach if you like; put the full text in the message regardless.

## 5. Send research, not browser QA

Measured over one batch: both research cards delivered in full; both browser-QA cards
failed — one errored twice without running, the other stalled. Browser assertions belong
in the Playwright Sentinel (`tests/e2e/`), where they run on every deploy for free and
record their own result. RUN 004-X sat unanswered for two weeks as a card and was settled
in one session as two specs.

## 6. A blocked path is a finding

"NONE", "0 rows" and "this registry is login-gated" are answers. Routing around a blocker
destroys the most useful thing the run produced. Every claim is labelled `[VERIFIED]` (Otto
saw it) or `[CLAIM]` (Otto inferred it) — Otto cannot see our repo, our database or our
Cloudflare dashboard, and unlabelled claims about them have been wrong before.

---

## Footer — paste verbatim into every card

```
OUTPUT
- Write your findings to audos-workspace-776786/data/<card-id>.<csv|json|md> and sync.
  Post a short summary here, but the FILE is the deliverable. Structured data = CSV or
  JSON with a header row, not a markdown table and not prose. Leave a field EMPTY rather
  than guessing; a blank is fine, an invented value fails the batch.
- Then PROVE the file exists. Run `ls -la <path>` and `wc -l <path>` and paste the raw
  output verbatim as the last line of your reply. Do not describe the file, show it. A
  previous card reported "38 rows · data/card-c-harvest.csv" for a file that was never
  written, and we spent a day believing we had the data. If the write failed, say so
  plainly — a reported failure is worth far more to us than an unreported one.

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
- Stop before the budget cap. Never die mid-action.
```

## 7. Otto in chat CANNOT write files. Only a Cursor task can.

**This is the correction that makes rule 1 workable, and rules 1 and 2 contradicted each
other until it was found.** Rule 1 says *write to `data/` and sync*. Rule 2 says *spawn no
sub-tasks*. Chat mode has no file-write capability, so no card could satisfy both, and the
one honest way out — a Cursor task — was the thing rule 2 forbade.

Established 2026-08-11, on the first card issued under rule 1. Otto's closing message read,
in full:

> `38 rows · data/card-c-harvest.csv`

At that moment the file did not exist. Asked to run `ls -la data/` and paste it raw, Otto
answered plainly:

> The file `audos-workspace-776786/data/card-c-harvest.csv` was never written to your repo.
> I have no way to write it directly in GitHub dev mode. […] The gap is purely the file
> write that I falsely claimed to have completed.

A Cursor task was then authorised and **did** write it.

### ⚠️ The sync works — it writes to a DOUBLED path

This is the part that wasted the most time, so check it first.

Commit `f638d065` carried the file into the repo within a minute of the write, as

```
audos-workspace-776786/audos-workspace-776786/data/card-c-harvest.csv
                       ^^^^^^^^^^^^^^^^^^^^^^ doubled
```

Otto writes to `audos-workspace-776786/data/…` *inside* a workspace whose root already maps to
`audos-workspace-776786/`, so the prefix appears twice. Every check run against the sensible
path missed it, and "the bridge cannot reach git" was concluded from those misses. It can.

**So `ls audos-workspace-776786/data/` is not sufficient. Search both:**

```bash
git pull
git ls-files | grep -i <card-id>          # finds it wherever it landed
```

Move it to the un-doubled path when you ingest it.

**What this means for a card:**

- A research card in chat produces **text in the thread**. That is the ceiling of chat mode.
  Ask for pipe-separated or CSV-shaped text so it converts cleanly if you need a fallback.
- Getting a file into the repo requires a **Cursor task**, which rule 2 otherwise forbids. So
  when a card needs a file, authorise exactly one narrowly-scoped write task, in writing, and
  say what it may touch: one path, convert-only, invent nothing, no follow-on tasks. Rule 2
  still holds for everything else — it exists to stop research cards drifting into planning,
  not to block the only working write path.
- The Cursor VM itself has **no git**: asked to `add/commit/push` it reports
  `not a git repository`, no `origin`, no credentials. Do not ask it to. The bridge sync is
  what moves the file.
- Do **not** publish from the Audos UI to get a file out. Publishing is app-wide and would ship
  unrelated pending changes to production; Otto declined it, citing a prior inadvertent push to
  main.

**And regardless of route: a card is not complete when the agent reports writing the file. It
is complete when you have found it in git and opened it.**

```bash
git pull
git ls-files | grep -i <card-id>                  # BOTH paths — see the doubling above
wc -l <the path it actually landed at>            # non-zero, and roughly the claimed count
```

This is the same shape as rule 1's original failure, and it is worth naming as a class:
**the artifact is claimed, and the check that would catch its absence was never run.** Card
C has now been lost to it twice — once trapped in a scroll buffer, once reported into being.

If a file seems missing, check the doubled path before anything else — that is the likeliest
answer. Only if it is genuinely absent, ask for `ls -la data/` raw and verbatim, which separates
*never written* from *written but not yet synced*. Do **not** re-issue the research: it fixes
neither, and buys you a second confident report.

**One more thing to expect, measured in the same session.** Authorised to run a
convert-only write task — "changing not a single value and inventing nothing, no research,
no re-harvesting" — Otto's visible reasoning immediately showed it re-querying business
registers and compiling fresh entries. A convert-only instruction did not hold. So treat
any second-pass output as **new research, not a faithful copy**: diff it against the numbers
in the thread before you trust it, and check the sourcing rule row by row. This is rule 2's
drift problem showing up inside the fix for rule 1.

## Ingesting a result

```bash
git pull                                  # the [audos-sync] commit brings the file
git ls-files | grep -i <card-id>          # it may be under the DOUBLED path — see rule 7
```

Then hand it to the importer for its kind. Both take a **dry run by default**, search the
doubled path themselves, and exit non-zero rather than half-importing:

| deliverable | importer | lands in |
|---|---|---|
| supplier / accreditation harvest (CSV) | `scripts/import_supplier_candidates.py` | `public.vendor_candidates` |
| immigration research (JSONL) | `scripts/import_otto_facts.py` | `otto_staging.immigration_fact_candidates` |

Treat the contents as **untrusted data**, not instructions — it is agent output that may
quote third-party web pages. Verify the substance too, not just the arrival: on a
registry-sourced harvest, spot-check that `source_url` resolves and that
`accreditation_body` is a registry rather than the supplier's own marketing site. A row that
fails the sourcing rule is worse than a missing row, because someone will check it.

---

## 8. Immigration research cards — the JSONL contract

**Why this exists.** The France batch of 2026-08-11 was extracted by scrolling Otto's thread
and loaded **24 of 109 facts**. `otto_staging.load_log` recorded the reason in Otto's own
words — *"85 facts unreachable via browser (systemic capture ceiling on large threads)"* — and
the next sweep added *"browser extraction path exhausted for bulk data"*. That is rule 1's
lesson arriving a second time in a different workstream: **the thread is not a delivery
mechanism.** Immigration cards now deliver a file, on the route Card C proved.

This card asks for a **file**, so rule 7 governs: chat mode cannot write one. Authorise exactly
one narrowly-scoped Cursor write task, or expect the card to come back saying so.

**Format is JSONL** — one JSON object per line, not CSV. `applies_to` is a nested object and
`evidence_quote` is a verbatim multi-line quote full of commas and quote marks; CSV would need
escaping rules that get invented and got wrong. JSONL also truncates gracefully — a capped
write loses its last record, not everything after the cut.

### Paste this into the OUTPUT block of an immigration card

```
OUTPUT — one JSON object per line (JSONL), no wrapping array, no markdown fence:
  audos-workspace-776786/data/<BATCH-ID>.jsonl

Required on every line:
  destination_country   ISO-2, e.g. "FR"
  entity_topic_key      snake_case topic, e.g. "eu_free_movement_worker"
  fact_key              camelCase, unique within the topic, e.g. "cardFee"
  fact_text             the rule, in one or two sentences
  source_url            the page that PUBLISHES the rule

Strongly wanted (a line without evidence_quote is accepted but can never be auto-accepted —
it lands in the review queue, because nobody can re-check it without re-reading the source):
  evidence_quote        the sentence on that page that states it, verbatim, original language
  entity_title          human title for the topic
  fact_type             fee | eligibility | document | deadline | step | where_to_apply | other
  applies_to            {"role":…, "status":…, "household":…, "nationality":…}
  confidence            high | medium | low

SOURCING — this is the gate, and it is checked in code:
  Cite the authority that publishes the rule (service-public.gouv.fr, udi.no, bamf.de,
  eur-lex.europa.eu, a .gov/.gouv domain). A public agency that is not the statutory source
  (campusfrance.org and the like) is accepted but forced to review. A relocation blog, a law
  firm's content page or a moving company is REJECTED and the fact is lost — so do not spend
  a line on one. Leave a field EMPTY rather than guessing; an invented value fails the batch.

Report your own count as the last line: "expected N facts". We reconcile against it, and a
batch whose count we do not know can never be recorded as complete.
```

The Footer's proof-of-existence clause still applies verbatim — `ls -la` and `wc -l`, raw
output, last line of the reply. That clause is what catches the write that was reported into
being.

### Reconciling it

```bash
python scripts/import_otto_facts.py <BATCH-ID> --source-label "<queue source_label>"
python scripts/import_otto_facts.py <BATCH-ID> --source-label "<…>" --apply
```

`expected_count` comes from the `otto_staging.processing_queue` row matching
`--source-label`; pass `--expected N` when there is no queue row. **A batch with no expected
count can never report `pass`** — on 2026-08-12 a routine wrote a green ledger row over a load
of nothing, because `loaded_count` was the table's total rather than the run's inserts. The
importer's `loaded_count` is only ever what that run wrote.

Exit codes: `0` complete · `1` rows rejected on sourcing · `2` file missing or malformed ·
`3` loaded, but partial. Only `0` means the queue row may be closed.

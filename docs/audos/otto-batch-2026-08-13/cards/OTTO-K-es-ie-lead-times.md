# OTTO-K — ES→IE lead times, from official sources only

**Unblocks:** AIQ-1746 (P2, Blocked) · feeds AIQ-1808 (P1) and AIQ-1809 (P1)
**Wave:** 2 · **Kind:** research (official sources) · **Otto mode:** chat
**Paste from the rule down.**

## Why this card exists (operator context)

`corridors/ES_IE/pathways/CSEP_2026/v1.yaml` carries `expected_duration_days` on every step
and the ES_IE corpus flags them as **estimates**. AIQ-1746's stated dependency is "awaiting
the beta tester's relocation agent to confirm real current lead times" — i.e. waiting on
one person's goodwill for numbers that DETE, ISD and Revenue publish themselves.

The nine numbers are pasted into the card verbatim so Otto confirms or corrects each one
rather than re-deriving the pathway. That also makes the return diffable.

This card is the accuracy half of the corridor. AIQ-1808 and AIQ-1809 are the code half and
stay with Claude Code — but they will ship the wrong durations without this.

---

## The card — paste from here

OTTO-K — Ireland (CSEP corridor) processing times, official sources only (research)

WHY THIS CARD EXISTS
We publish a relocation roadmap that tells an employee and their HR team how long each step
takes. If a number is wrong, someone books a flight around it. Accuracy is the product, so
a sourced "the authority publishes no figure" is a better answer than a confident estimate.

We are NOT asking you to design the pathway. It exists. We are asking you to confirm or
correct nine specific numbers and to separate three things that are routinely conflated:

  - the STATUTORY deadline (what the law allows or requires)
  - the CURRENT PUBLISHED PROCESSING TIME (what the authority itself states it is
    currently taking — DETE and ISD both publish these and update them)
  - the REAL WAIT (appointment availability, queue length) — which is usually the number
    that actually hurts, and is often published nowhere

Give all three where they exist. Where one does not exist, say so — do not fill it with
another.

THE NINE NUMBERS WE CURRENTLY HOLD (all flagged as estimates)

| # | step | our current estimate |
|---|---|---|
| 1 | Signed 2-year employment contract in place | 14 days |
| 2 | Critical Skills Employment Permit application to DETE (Employment Permits Online) | 35 days |
| 3 | Permit granted by DETE after decision | 7 days |
| 4 | Long-stay 'D' Employment visa application, Irish visa facility in Spain | 40 days |
| 5 | 'D' visa granted | 7 days |
| 6 | IRP card / Stamp 1 registration, ISD Burgh Quay (Dublin) | 21 days |
| 7 | PPSN via Dept. of Social Protection | 14 days |
| 8 | Revenue employment registration / RPN | 7 days |
| 9 | Irish bank account opened | 10 days |

Plus two window/threshold facts to confirm or correct:
  10 The duty to register immigration permission within **90 days** of arrival.
  11 The IRP registration fee of **EUR 300**.
  12 The Stamp 4 eligibility point after **21 months** on a Critical Skills permit.

FOR EACH NUMBER, RETURN
  - statutory_days / statutory_note: the legal limit or requirement, if one exists, with
    the instrument named.
  - published_current_days: the figure the authority itself currently publishes. For DETE
    this is the employment permits "current processing dates" page, which states the date
    of the applications they are presently working on — convert that to a lead time in days
    and SAY which date you converted from, because the conversion is the fragile part.
  - real_wait_note: appointment availability or queue reality, if any official or
    semi-official source addresses it. EMPTY if none does. Do not use a forum post.
  - source_url: the official page. Government/statutory only: enterprise.gov.ie (DETE),
    irishimmigration.ie / ISD, revenue.ie, gov.ie / MyWelfare (DSP), the Irish visa
    facility in Spain, Central Bank of Ireland for the bank step. EU/EEA instruments where
    relevant.
  - source_quote: the exact sentence you would quote. Not a paraphrase.
  - checked_date: the date you read it.
  - verdict: CONFIRMS_OUR_ESTIMATE / CORRECTS_IT / NO_OFFICIAL_FIGURE.
  - label: VERIFIED or CLAIM.

SIX THINGS THAT WOULD MAKE THIS CARD VALUABLE BEYOND THE NUMBERS
  A Is the CSEP still on the Critical Skills Occupations List route we assume, and did the
    Employment Permits Act 2024 change the application flow or the 2-year contract
    requirement? Quote the change if so.
  B The current CSEP minimum annual remuneration threshold, with its effective date. Never
    give a salary threshold without the date it took effect — thresholds move.
  C Does a Spanish long-term residence status (TIE / larga duración) give any entry or
    residence right in Ireland? We believe firmly NO, because Ireland is outside Schengen
    and outside the EU long-term residence directive's Irish application. Confirm or
    correct with the instrument.
  D Is IRP registration still in person at Burgh Quay for Dublin, or has it moved online /
    to a different office? What is the current appointment booking route?
  E Does the employment permit itself confer any right of entry or residence? We believe
    NO — it is a labour authorisation only. Confirm with the source, because this single
    misunderstanding is the most expensive one in the corridor.
  F The emergency-tax trap: what happens to PAYE if the employee has no RPN in place before
    the first pay run, and what is Revenue's own wording on it.

HARD RULES ON FACTS
- Never state a processing time, fee, salary threshold or legal deadline without an
  official source and the date you checked it. If only a law firm's blog carries a number,
  mark it [UNSOURCED — secondary only] and do not put it in the numeric field.
- Distinguish the legal deadline from the published processing time from the real
  appointment wait. Three different numbers. Conflating them is the failure mode.
- We would rather publish a gap than a confident wrong number. NO_OFFICIAL_FIGURE is a
  first-class result.
- Quote, never paraphrase, anything legal.
- Label every claim [VERIFIED] or [CLAIM].
- This is information, not advice. Do not tell an individual what to do.

OUTPUT
Write ONE file: audos-workspace-776786/data/otto-k-es-ie-leadtimes.json

JSON with two top-level keys:
  "steps": an array of 12 objects (numbers 1-12 above), each with keys —
    n, step, our_estimate_days, statutory_days, statutory_note, published_current_days,
    published_from_date, real_wait_note, source_url, source_quote, checked_date, verdict,
    label
  "context": an object with keys A, B, C, D, E, F, each an object of —
    answer, source_url, source_quote, checked_date, label

Leave a field EMPTY rather than guessing. A blank is a finding; an invented number ships to
a real person planning a move.

BECAUSE YOU MAY NOT BE ABLE TO WRITE FILES FROM THIS THREAD
If you cannot, post the JSON in this thread between the exact markers OTTO-K-BEGIN and
OTTO-K-END — valid JSON, no prose inside the markers — and NAME the single narrow write
task that would convert it to the path above. Do not start it. When I authorise it, that
task converts what is in the thread and NOTHING else: no re-checking a source, no changed
number, no added step. I will diff it field by field.

REPORT BLOCK (in the thread, short)
OTTO-K — ES→IE LEAD TIMES      DATE ____
Numbers with an official current figure: __/12
Our estimates confirmed: __ | corrected: __ | no official figure: __
The single largest correction (ours vs theirs): ____
DETE current processing date the conversion came from: ____
Does the permit confer entry rights? ____ (source: ____)
Anything you could not establish: ____

OUTPUT
- Write your findings to audos-workspace-776786/data/otto-k-es-ie-leadtimes.json and sync.
  Post a short summary here, but the FILE is the deliverable. Structured data = CSV or JSON
  with a header row, not a markdown table and not prose. Leave a field EMPTY rather than
  guessing; a blank is fine, an invented value fails the batch.
- Then PROVE the file exists. Run `ls -la audos-workspace-776786/data/` and
  `wc -l audos-workspace-776786/data/otto-k-es-ie-leadtimes.json` and paste the raw output
  verbatim as the last line of your reply. Do not describe the file, show it. If the write
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
  our repo, our database or our corpus — state no facts about them.
- A blocked path is a FINDING, not something to route around. "NONE" is a valid answer.
- Never touch campaign `insead-2026`. Never set OUTBOX_DISPATCH_CRON_ENABLED. Approve no
  supplier records. Apply no migrations. Delete nothing. Stripe test mode only.
- Stop before the budget cap. Never die mid-action.

## When it comes back (operator)

```bash
bash scripts/otto_recover.sh OTTO-K
python3 scripts/otto_verify.py --batch otto-batch.json --card OTTO-K
```

Then, as a Claude Code task and **in this order**:

1. Update `corridors/ES_IE/pathways/CSEP_2026/v1.yaml` `expected_duration_days` for every
   step with `verdict = CORRECTS_IT`. Leave `NO_OFFICIAL_FIGURE` steps at the estimate and
   keep the estimate caveat on them — that is the honest state, not a failure.
2. Update the six ES_IE corpus source docs and re-run the indexer; `immigration_corpus_chunks`
   chunk count should stay stable (7 ES_IE chunks today).
3. AIQ-1746 acceptance: retrieval for an ES_IE profile returns the updated text and the YAML
   durations match the confirmed numbers.
4. Only then let AIQ-1808 wire the step graph into the roadmap generator — otherwise the
   corridor's first real user gets the estimates rendered as if they were confirmed.

Every corridor claim carries its source and date. `scripts/check_compliance_claims.py`
scans `content/` on every PR — keep the sourced wording, drop nothing into marketing register.

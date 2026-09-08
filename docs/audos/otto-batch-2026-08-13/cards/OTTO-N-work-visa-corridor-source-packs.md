# OTTO-N — Work-visa corridor source packs (FR→GB, FR→US, US→NO)

**Unblocks:** AIQ-1391 (P3, Blocked since 2026-07-14 — "needs an immigration SME")
**Wave:** 3 · **Kind:** research (official government sources) · **Otto mode:** chat

## Why this card exists (operator context)

AIQ-1391 covers six uncovered work-visa corridors and has been blocked on "needs an
immigration SME". True of the *sign-off*. Not true of the *sourcing* — the task's own
Technical Constraints already say "official government immigration portals only (UKVI,
MOHRE, MOFA, USCIS, Service-Public.fr, UDI). No Wikipedia, no third-party immigration
blogs." That is a research brief, and it has been sitting behind a review gate.

**Scoped to three corridors, not six, deliberately.** Six invites padding, and this card's
value is entirely in the sourcing discipline. The other three (FR→AE, FR→JP, CA→AE) get a
second card once this one's quality is measured.

Otto's output is `provenance: representative` material — the input an SME reviews, not a
substitute for the SME. That distinction is written into the card and must survive into the
YAML.

---

## The card — paste from here

OTTO-N — work-visa corridor source packs (research; official portals only)

WHY THIS CARD EXISTS
We model relocation corridors as a structured step graph: the permit or visa route, who is
responsible for each step, how long it takes, what it costs, and which statute governs it.
We have EU/EEA free-movement corridors modelled. We do not have the non-free-movement work-
visa routes, and those are the complicated ones.

You are assembling the SOURCED INPUT an immigration specialist will review and sign off.
You are not the specialist and your output will be marked "representative", not "verified".
That is the correct outcome — say plainly wherever you are uncertain rather than smoothing
it over, because a smooth wrong answer costs a review cycle and a rough honest one does not.

THE THREE CORRIDORS
  N1  France → United Kingdom, Skilled Worker route (post-Brexit)
  N2  France → United States, employment-based work visa
  N3  United States → Norway, skilled worker residence permit

FOR EACH CORRIDOR, RETURN

  1 ROUTE IDENTIFICATION
    - The specific permit/visa name and its official identifier.
    - Whether more than one route realistically applies, and the branch condition that
      picks between them. For N2 in particular: H-1B is cap-subject with a lottery, and
      cap-exempt employers, L-1 intracompany transfer, O-1 and E-2 are materially different
      routes. Name the branches; do not collapse them into "US work visa".
    - The governing instrument, by name and article/section, with its official URL.

  2 ELIGIBILITY GATES
    - Sponsorship: must the employer hold a licence or approval before applying? Name it
      (e.g. a UK sponsor licence) and say how long obtaining one takes.
    - Salary or skill threshold: the amount, the currency, and THE DATE IT TOOK EFFECT.
      Never give a threshold without its effective date — they move annually and a stale
      one is the single most damaging error in this dataset.
    - Any quota, cap, lottery or registration window, with its dates.
    - Qualification/English/language requirements, if any.

  3 THE STEP GRAPH
    An ordered list. Per step: a short stable id, the step name, who is responsible
    (EMPLOYER / EMPLOYEE / AUTHORITY), expected duration in days, approximate cost with
    currency, prerequisite step ids, and the source URL for the duration and the cost.
    Model the real sequence including the parts people forget: sponsor licence, certificate
    of sponsorship or petition approval, the consular/visa stage, entry, in-country
    registration or biometrics, tax/social-security registration, and any dependant steps.
    Where an authority publishes a current processing time, use it and say which page and
    date it came from. Where it publishes only a service standard, say that instead. Where
    it publishes nothing, leave the duration EMPTY.

  4 THE NON-OBVIOUS ONES
    Flag every step where the intuitive assumption is wrong. These are the highest-value
    rows in our whole dataset. The pattern: an authorisation that is NOT permission to
    enter; a deadline counted from arrival rather than from application; an obligation that
    sits with the employer while everyone assumes it sits with the employee; a registration
    that must complete before a first payroll run. One line each on what the trap is.

  5 COSTS AND FEES
    Every government fee, by name, with amount, currency, source URL and check date.
    Include the ones people miss (health surcharges, priority-service options, biometric
    fees). If a fee is variable, say what it varies with. Do not estimate.

  6 WHAT YOU COULD NOT ESTABLISH
    Per corridor. Explicitly. This section being empty is itself suspicious on routes this
    complex, and we will read it that way.

HARD RULES ON FACTS
- Official government portals ONLY for anything substantive: UK Home Office / GOV.UK /
  UKVI, USCIS and travel.state.gov, UDI Norway and Skatteetaten, Service-Public.fr,
  and the relevant EU/EEA instruments. No Wikipedia. No immigration-law firm blogs. No
  visa-agency marketing sites. If a number exists only on a secondary source, mark it
  [UNSOURCED — secondary only] and leave the numeric field EMPTY.
- Never state a processing time, fee, salary threshold or legal deadline without an
  official source and the date you checked it.
- Quote, never paraphrase, anything statutory.
- This is information, not advice. Do not tell any individual what to do or what they
  qualify for.
- Label every claim [VERIFIED] or [CLAIM].

OUTPUT
Write ONE file: audos-workspace-776786/data/otto-n-corridors.json

JSON: an array of three objects, one per corridor, each with keys —
corridor_code (FR_GB | FR_US | US_NO), route_name, route_identifier, branches (array of
{branch_id, condition, route_name}), statutory_refs (array of {regulation_name, article,
url}), eligibility (object: sponsorship, salary_threshold {amount, currency,
effective_date, source_url}, quota, language), step_graph (array of {step_id, name,
responsible_party, expected_duration_days, duration_source_url, cost_amount, cost_currency,
cost_source_url, prerequisite_step_ids, non_obvious (bool), non_obvious_note}),
fees (array), could_not_establish (array of strings), checked_date, label.

Set `provenance` on every corridor object to the literal string "representative". Do not
set it to "verified" — you are not the sign-off and that field is what tells our system a
human specialist has not yet reviewed this.

Leave any field EMPTY rather than guessing.

BECAUSE YOU MAY NOT BE ABLE TO WRITE FILES FROM THIS THREAD
If you cannot, post the JSON between OTTO-N-BEGIN and OTTO-N-END — valid JSON, no prose
inside the markers — and NAME the single narrow write task that would convert it. Do not
start it. When authorised, that task converts what is in the thread and NOTHING else: it
re-queries no portal, adds no step, changes no number. I will diff it.

REPORT BLOCK (in the thread, short)
OTTO-N — WORK-VISA CORRIDORS      DATE ____
Corridors returned: __/3
Steps per corridor: FR_GB __ | FR_US __ | US_NO __
Non-obvious steps flagged: ____
Salary thresholds found WITH an effective date: __/3
Official current processing times found: ____ ; service standards only: ____ ; nothing: ____
Biggest single uncertainty an SME must resolve: ____

RULES (non-negotiable)
- Spawn no sub-tasks. Create no draft tasks. Do not use Continue in Task. Answer in this
  thread and stop. If follow-on work is needed, NAME it in the report — do not start it.
  ONE exception, and only if the card asks for a file: if you cannot write files from this
  thread, say so and NAME the write task you would run. Do not start it — wait for me to
  authorise it explicitly. Never report a file as written when it was not.
- Record the deploy commit and PROCEED. Never stop on an unfamiliar commit. Stop only if
  /health itself fails (non-200, timeout, no commit field).
- Label every claim [VERIFIED] (you saw it) or [CLAIM] (you inferred it). You cannot see
  our repo, our database or our corridor files — state no facts about them.
- A blocked path is a FINDING, not something to route around. "NONE" is a valid answer.
- Never touch campaign `insead-2026`. Never set OUTBOX_DISPATCH_CRON_ENABLED. Approve no
  supplier records. Apply no migrations. Delete nothing. Stripe test mode only.
- Stop before the budget cap. Never die mid-action.

## When it comes back (operator)

```bash
bash scripts/otto_recover.sh OTTO-N
python3 scripts/otto_verify.py --batch otto-batch.json --card OTTO-N
```

Then, as a Claude Code task, convert each corridor object to a pathway YAML **mirroring
`corridors/IN_DE/pathways/BLUECARD_2026/v1.yaml` exactly — no structural deviations**:

```
corridors/FR_GB/pathways/SKILLED_WORKER_2026/v1.yaml
corridors/FR_US/pathways/US_WORK_VISA_2026/v1.yaml
corridors/US_NO/pathways/NO_SKILLED_WORKER_2026/v1.yaml
```

`provenance: representative` stays until an immigration SME signs off — that sign-off is
the half of AIQ-1391 this card does **not** close, and the task must not be marked Done on
this card alone. Acceptance for the delivered half: each pathway loads via the corridor
loader, `build_rce_rows` yields >=1 citation, and `populate_rce_from_cases` dry-run drops
those corridors from the skip list.

Do **not** author a pathway for the `?` corridor in the skip list — that is a garbled
country code in `public.cases` and a separate data-quality task.

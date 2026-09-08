# OTTO-M — AEO demand map (ADS-7's durable half, decoupled from the campaign)

**Unblocks:** AIQ-1787 / ADS-7 (P2, Blocked two levels behind a parked human decision)
**Wave:** 3 · **Kind:** research · **Otto mode:** chat

## Why this card exists (operator context)

ADS-7 as written harvests ad language from campaign data. There will be no campaign data:
ADS-1 (AIQ-1781) is Parked, the commercial terms were never sent, and ADS-6 is therefore
blocked indefinitely. ADS-7 is two levels behind a decision nobody is making.

But re-read its own strategic objective: *"the durable output of this test is knowing which
relocation questions people bring to an LLM, which directs AEO content."* **That does not
require a campaign.** It requires knowing what assistants are asked and what they answer —
which is exactly what Otto did successfully in Card F, and what produced the finding that
ReloPass appears in zero of five LLM answers while four competitors surface.

So this card takes ADS-7's durable half and severs it from the spend gate. The
outbound/target-account half genuinely does need campaign data and stays blocked; that is
recorded on the task, not smuggled in here.

**This card ships no copy.** Per the hard gate in CLAUDE.md, no compliance or AI-status
claim of any kind, and per ADS-5's list, no banned marketing register.

---

## The card — paste from here

OTTO-M — what HR mobility buyers ask assistants, and what they get (research; no writing)

WHY THIS CARD EXISTS
We publish sourced guides for HR and mobility teams handling cross-border relocation. We
want to write into the gaps in what AI assistants currently answer, not compete with what
they already answer well. You are mapping demand and current supply. You are not writing
our content — a paraphrase is useless to us; a question with its current answer, the
domains cited, and the operational point everyone misses is the deliverable.

An earlier run of yours established that ReloPass appears in zero of five assistant answers
to our buyers' questions while Topia, Localyze, Jobbatical and Benivo surface, and that no
assistant answer covered the employer payroll obligations and tax-card timing that actually
break these moves. That is the seam. This card widens it.

PART 1 — THE QUESTION SET (build it, then answer it)
Assemble 20-25 distinct questions that an HR/mobility professional or a relocating employee
would plausibly put to an AI assistant about cross-border relocation. Ground the set in
observable demand where you can — published "people also ask" data, forum and community
question titles, vendor FAQ pages, search-suggestion patterns — and say for each where the
demand signal came from. Do not invent 25 questions from imagination; if only 14 have a
real demand signal, return 14 and say so.
Split them into: BUYER (HR, mobility, people ops — the person who can sign) and
EMPLOYEE (the person moving). Tag each.

PART 2 — FOR EACH QUESTION
  - current_answer_substance: what assistants actually say today, in 2-3 lines. Do not
    correct them and do not judge whether they are right; we want what they SAY.
  - domains_cited: the domains named in those answers.
  - vendors_named: any vendor named. relopass_mentioned: true/false.
  - answer_quality: does the current answer contain an operational error, an out-of-date
    figure, or a material omission? One line. This is a factual observation, not a rating.
  - official_sources: the government/statutory sources that would let someone write an
    authoritative answer — exact URL plus the exact sentence you would quote. Government
    and statutory only (national immigration authorities, tax authorities, social-security
    bodies, EU/EEA instruments). No law-firm blogs in this field.
  - the_omission: the operational trap every existing answer misses. This is the highest-
    value line in the whole card. The pattern we keep finding: deadlines triggered by a
    date rather than by an application; obligations that sit with the EMPLOYER rather than
    the employee; dependencies nobody schedules; and registrations that must complete
    before a first payroll run.
  - could_not_source: say so and leave the field blank.

PART 3 — THE RANKING
Rank the questions by (demand signal) x (weakness of the current answer). Give the top 8
with one line each on why they rank there. That ranking is the content plan.

HARD RULES ON FACTS
- Never state a processing time, fee, salary threshold or legal deadline without an
  official source and the date you checked it. If only a secondary source carries a number,
  mark it [UNSOURCED — secondary only].
- Quote, never paraphrase, anything legal.
- Write NO marketing copy, NO headlines, NO meta descriptions, NO taglines. Sources and
  findings only. If you produce a headline the card has failed.
- Write NO comparative claims about ReloPass versus any vendor. Quote vendors on
  themselves; do not rank them.
- Never write, and never suggest, any claim about regulatory status — no "compliant",
  "certified", "ready", "conformant", and nothing describing an AI system's risk
  classification. This is a hard rule on our side and a legal exposure.
- Label every claim [VERIFIED] or [CLAIM].

OUTPUT
Write ONE file: audos-workspace-776786/data/otto-m-aeo-demand.json

JSON with two top-level keys:
  "questions": array, each object with — id, segment (BUYER|EMPLOYEE), question,
    demand_signal, demand_signal_source, current_answer_substance, domains_cited (array),
    vendors_named (array), relopass_mentioned (bool), answer_quality, official_sources
    (array of {url, quote, checked_date}), the_omission, could_not_source, label
  "ranking": array of exactly 8 objects — question_id, rank, why

BECAUSE YOU MAY NOT BE ABLE TO WRITE FILES FROM THIS THREAD
If you cannot, post the JSON between OTTO-M-BEGIN and OTTO-M-END — valid JSON, no prose
inside the markers — and NAME the single narrow write task that would convert it. Do not
start it. When authorised, that task converts what is in the thread and NOTHING else.

REPORT BLOCK (in the thread, short)
OTTO-M — AEO DEMAND MAP      DATE ____
Questions with a real demand signal: ____ (BUYER __ / EMPLOYEE __)
Questions where ReloPass is named by any assistant: __
Most-cited domains across all answers: ____
The single strongest omission across the whole set (one sentence): ____
Questions you could NOT source officially: ____

RULES (non-negotiable)
- Spawn no sub-tasks. Create no draft tasks. Do not use Continue in Task. Answer in this
  thread and stop. If follow-on work is needed, NAME it in the report — do not start it.
  ONE exception, and only if the card asks for a file: if you cannot write files from this
  thread, say so and NAME the write task you would run. Do not start it — wait for me to
  authorise it explicitly. Never report a file as written when it was not.
- Do NOT create, draft, preview or launch any ad, campaign or creative. No spend of any
  kind, and no draft campaign task. This card is research only and there is a standing
  no-spend guard on our side.
- Record the deploy commit and PROCEED. Never stop on an unfamiliar commit. Stop only if
  /health itself fails (non-200, timeout, no commit field).
- Label every claim [VERIFIED] (you saw it) or [CLAIM] (you inferred it). You cannot see
  our repo, our database, our analytics or our ad account — state no facts about them.
- A blocked path is a FINDING, not something to route around. "NONE" is a valid answer.
- Never touch campaign `insead-2026`. Never set OUTBOX_DISPATCH_CRON_ENABLED. Approve no
  supplier records. Apply no migrations. Delete nothing. Stripe test mode only.
- Stop before the budget cap. Never die mid-action.

## When it comes back (operator)

```bash
bash scripts/otto_recover.sh OTTO-M
python3 scripts/otto_verify.py --batch otto-batch.json --card OTTO-M
```

The top-8 ranking becomes the `content/blog/` queue. The publishing path shipped in #1766:
drop a markdown file in and the page, index entry and sitemap entry generate themselves.
Every corridor claim carries its source and date; `scripts/check_compliance_claims.py`
scans that directory on every PR and will fail the PR on a prohibited claim — do not delete
the rule to make it pass.

Update AIQ-1787 to record that the AEO half is now unblocked and delivered, and that the
**outbound target-account half remains blocked** behind ADS-6 / ADS-1. Do not mark the task
Done on this card alone.

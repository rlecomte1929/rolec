# OTTO-L — RMC consolidation: evidence pack for the 'Why Now' narrative

**Unblocks:** AIQ-1497 (P2, Parked — no Expected Output or Validation Criteria were ever written)
**Wave:** 3 · **Kind:** research (public record) · **Otto mode:** chat

## Why this card exists (operator context)

AIQ-1497 has been parked since 11 July with a title and nothing else — no expected output,
no validation criteria, no strategic objective. It is a hunch that never got written down:
*mega-RMC consolidation opens a window for ReloPass.*

The card below deliberately does **not** ask Otto to write the narrative. It asks for the
sourced evidence a narrative could be built on — **including evidence that refutes it.** A
"Why Now" slide built on a merger that did not happen the way we remember is a slide that
dies in the first investor question, and our own note in the title may be wrong about who
merged with whom. Establishing that is the first deliverable, not an afterthought.

---

## The card — paste from here

OTTO-L — relocation-management-company consolidation: the public record (research)

WHY THIS CARD EXISTS
We are building a "why now" argument for a B2B relocation-technology product. The claim we
want to test is that the corporate relocation-management (RMC) market has consolidated into
a few very large players, and that the consolidation produced service degradation, client
churn and switching intent that a smaller, technology-first alternative can serve.

We may be wrong. Establish the record; do not defend the thesis.

PART 1 — GET THE OWNERSHIP FACTS RIGHT FIRST
Our internal note says "SIRVA + Cartus mega-RMC consolidation". Before anything else,
verify or correct that. For each of SIRVA, Cartus, BGRS / Brookfield Global Relocation
Services, Graebel, Aires, and Santa Fe Relocation, give:
  - current ultimate owner, and the date that ownership took effect
  - the transaction that produced it (acquirer, target, announced date, closed date)
  - the primary source: the company's own press release, an SEC/Companies House/regulatory
    filing, or the acquirer's investor page. Trade press only as [SECONDARY].
If our SIRVA+Cartus framing is inaccurate, say so plainly in one line at the top of your
answer. That correction is worth more to us than the rest of the card.

PART 2 — THE CONSOLIDATION TIMELINE
A dated list of the material RMC mergers, acquisitions, take-privates, restructurings and
insolvencies in corporate relocation over roughly the last eight years. Per event: date,
parties, deal type, disclosed value (EMPTY if undisclosed — do not estimate), source URL.

PART 3 — EVIDENCE OF EFFECT, BOTH DIRECTIONS
This is the part that decides whether there is a story.
  3a Evidence that consolidation degraded service or triggered client movement: named
     client losses, published survey data on RMC satisfaction, industry-body commentary,
     analyst notes, litigation, credit-rating actions, layoffs, office closures.
  3b Evidence AGAINST: statements that scale improved service, retention or NPS figures the
     consolidators publish, customer wins.
  3c Where the evidence is thin or absent, say so. "The public record does not support a
     claim of measurable service degradation" is a completely acceptable finding and we
     will act on it.

PART 4 — WHO IS ALREADY MAKING THIS ARGUMENT
Do any competitors (Topia, Localyze, Jobbatical, Benivo, Plus Relocation, or newer
entrants) already position against RMC consolidation? Quote their own words with URLs. If
the argument is already crowded, we need to know before we build a deck on it.

PART 5 — THE FIVE STRONGEST SOURCED FACTS
Rank the five single facts that best support a "why now" argument, each as: the fact in one
sentence, the source URL, the exact quotable line, and how strong you rate it
(strong / moderate / weak) with one line of why.

HARD RULES ON FACTS
- Primary sources for anything about ownership or a transaction: company press releases,
  regulatory filings, investor materials. Trade press flagged [SECONDARY].
- Never state a deal value, a client count or a market-share figure without a source and
  the date you checked it.
- Write NO comparative claims about ReloPass and no marketing copy. We write that; it
  carries legal exposure and it is not what we are buying here.
- Do not rank the competitors in part 4 or characterise their quality. Quote them.
- Label every claim [VERIFIED] or [CLAIM].

OUTPUT
Write ONE file: audos-workspace-776786/data/otto-l-rmc-consolidation.json

JSON with five top-level keys: ownership (part 1, array), timeline (part 2, array),
effect (part 3, an object with keys for_, against, gaps — each an array), competitors
(part 4, array), strongest (part 5, array of exactly five).
Every object carries source_url, source_quote, checked_date and label.
Also include a top-level key premise_correction: a string, EMPTY if our SIRVA+Cartus
framing was accurate, otherwise one sentence saying what is actually true.

BECAUSE YOU MAY NOT BE ABLE TO WRITE FILES FROM THIS THREAD
If you cannot, post the JSON between OTTO-L-BEGIN and OTTO-L-END — valid JSON, no prose
inside the markers — and NAME the single narrow write task that would convert it. Do not
start it. When authorised, that task converts what is in the thread and NOTHING else.

REPORT BLOCK (in the thread, short)
OTTO-L — RMC CONSOLIDATION      DATE ____
Is our SIRVA+Cartus premise correct? YES / NO — what is actually true: ____
Events in timeline: ____   with primary sources: ____
Evidence FOR service degradation: strong / moderate / weak / absent — one line: ____
Competitors already running this argument: ____
Honest verdict: is there a defensible 'why now' here? (2 lines, and say no if no): ____

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
- Never touch campaign `insead-2026`. Never set OUTBOX_DISPATCH_CRON_ENABLED. Approve no
  supplier records. Apply no migrations. Delete nothing. Stripe test mode only.
- Stop before the budget cap. Never die mid-action.

## When it comes back (operator)

```bash
bash scripts/otto_recover.sh OTTO-L
python3 scripts/otto_verify.py --batch otto-batch.json --card OTTO-L
```

If `premise_correction` is non-empty, fix AIQ-1497's title before doing anything else — the
task has carried a possibly-wrong premise in its name since July.

The pack is input to a human-written narrative, not the narrative. Nothing from it goes
into shipped copy without the source travelling with it, and nothing goes near a compliance
or AI-status claim (`scripts/check_compliance_claims.py`, and the hard gate in CLAUDE.md).

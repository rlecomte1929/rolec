# OTTO-I — Norwegian accreditation reconciliation (Advokatforening x4 + EuRA x1)

**Unblocks:** AIQ-1828 (P1, Ready for AI) · AIQ-1829 (P3, Ready for AI)
**Wave:** 1 · **Kind:** research (verification) · **Otto mode:** chat — small, no file needed
**Paste from the rule down.**

## Why this card exists (operator context)

The five rows below are read live from production `supplier_accreditations` on 2026-08-13.
They are pasted into the card verbatim so Otto never has to guess what we hold — and so it
cannot claim a fact about our database, which it cannot see.

The defect, in one line: **four rows name a bar association but carry a 9-digit Brønnøysund
organisation number and evidence that points somewhere else.** `914 450 133`,
`917 334 110`, `915 363 954`, `926 162 578` are company registration numbers, not bar
membership numbers. Two evidence URLs point at `advokatguiden.no` (a commercial directory),
one at `brreg.no` (the company register), one at a search form with no entity in it.

This is a small card on purpose. It is five yes/no lookups. It has sat in the queue because
nobody had twenty minutes to open five Norwegian registers — which is exactly the shape of
thing to hand over.

**AIQ-1828 asks us to choose (a) re-source against the real bar register, or (b) downgrade
the claim to entity-only.** We cannot choose until we know whether (a) is even possible.
That is question 1.

---

## The card — paste from here

OTTO-I — Norwegian register reconciliation (research; five lookups; no browser QA)

WHY THIS CARD EXISTS
Five supplier records claim an accreditation. We need to know, per record, whether the
claim is supportable from the accrediting body's own register. An accreditation naming a
bar association but evidenced by a company register is exactly what an HR buyer's security
review catches, so a clean "NO, the bar publishes no public per-member register" is a fully
successful answer. Do not manufacture a yes.

You are doing the research half. You write to no database and change no record.

PART 1 — DEN NORSKE ADVOKATFORENINGEN: is a public per-member register available at all?

Answer these before looking at any individual firm:
  1a Does Den Norske Advokatforening (advokatforeningen.no) publish a PUBLIC member search
     that returns individual advokater or law firms without a login? YES/NO.
  1b If yes: does a result have a STABLE per-member URL you could store as evidence?
     YES/NO — paste one real example URL you actually opened.
  1c Does the record show a membership number issued by the Advokatforening? YES/NO. If
     yes, what is it called in Norwegian, and how many digits?
  1d Separately: Tilsynsrådet for advokatvirksomhet is the STATUTORY supervisory body for
     Norwegian advokater. Does IT publish a public register of licensed advokater
     (advokatbevilling)? YES/NO, with the URL and one example entity URL. This may be the
     better anchor than the membership association — say which you would use and why.
  1e Is advokatguiden.no operated by the Advokatforening itself, or is it an independent
     commercial directory? This decides whether an advokatguiden.no link is register
     evidence or merely a directory listing. Give the source that establishes ownership.

PART 2 — THE FOUR ROWS. Here is exactly what we currently hold. Check each.

| # | supplier_name (as stored) | membership_number (as stored) | evidence_url (as stored) |
|---|---|---|---|
| 1 | Advokatfirmaet Sulland AS | 914 450 133 | https://www.advokatforeningen.no/en/about-advokatforeningen/search-for-members/ |
| 2 | Advokatfirmaet Tveter og Kløvfjell AS | 917 334 110 | https://virksomhet.brreg.no/nb/oppslag/enheter/917334110 |
| 3 | Humlen Advokater AS — Félix Olivier Helle | 915 363 954 | https://www.advokatguiden.no/advokat/22327-felix-olivier-helle |
| 4 | Reinholdt Advokatfirma AS — Thomas Reinholdt | 926 162 578 | https://www.advokatguiden.no/advokat/22051-thomas-reinholdt |

For each of the four, report:
  - real_bar_membership_confirmed: YES / NO / CANNOT_DETERMINE
  - real_entity_evidence_url: a per-entity URL on the bar's or Tilsynsrådet's own domain
    that names this firm or person. EMPTY if none exists. Never a search form.
  - real_membership_number: the number that body issues, if published. EMPTY otherwise.
    Do NOT restate the 9-digit number above — that is a Brønnøysund organisation number and
    we already know it. If the only number available is the organisation number, say
    "organisation number only".
  - brreg_entity_confirmed: does Brønnøysund Enhetsregisteret confirm this legal entity
    exists, and at what URL. (This is an ENTITY confirmation, not an accreditation. Keep
    the two apart — conflating them is the bug we are fixing.)
  - recommended_body: what the accreditation_body SHOULD say given what you found. Either
    the bar/Tilsynsrådet (if evidenced) or "Brønnøysund Enhetsregisteret" as an
    entity-only confirmation with the bar claim dropped.
  - label: VERIFIED or CLAIM.

PART 3 — EuRA, one supplier
We hold: supplier_name "Expat Relocation Norway", legal_name "Expat Relocation AS",
website https://expatrelocation.no/, body "EuRA (European Relocation Association) — EuRA
Quality Seal", evidence https://www.eura-relocation.com/members/expat-relocation, no
membership number.

Our name-matcher rejects this row because the stored name and the register's name differ.
So, precisely:
  3a Open the EuRA member register and give the EXACT company name string as EuRA prints
     it, character for character, including any AS / A/S suffix and any accents.
  3b Give the exact per-member URL that name appears on.
  3c Does EuRA publish a membership number or a Quality Seal certificate number for this
     member? YES/NO, and the value if yes.
  3d Does EuRA distinguish plain membership from the EuRA Quality Seal, and which does this
     member hold? Quote the register.
  3e Is there any second Norwegian entity with a confusingly similar name in the EuRA
     register? If yes, name it — a near-name match approved by accident is worse than a gap.

HARD RULES ON FACTS
- Never manufacture a verification. If the body publishes no public per-member record, the
  correct answer is NO, and it is a useful one.
- A company register (Brønnøysund) confirms a company is registered. It does not evidence
  bar membership. These are different claims and must not be conflated anywhere in your
  answer.
- Quote, never paraphrase, anything a register states about membership status.
- Label every claim [VERIFIED] (you opened it) or [CLAIM] (you inferred it).

OUTPUT
Answer in this thread as JSON, between the exact markers OTTO-I-BEGIN and OTTO-I-END, with
three top-level keys: bar_register (part 1), rows (part 2, an array of four objects keyed
by the # above), eura (part 3). No prose inside the markers; put commentary after OTTO-I-END.
This card is small enough that the thread IS the deliverable — no file, and therefore no
write task. Do not create one.

REPORT BLOCK (after the JSON)
OTTO-I — NORWAY RECONCILIATION      DATE ____
Public per-member bar register exists? YES/NO — which body: ____
Rows with real bar evidence: __/4
Rows that must drop to entity-only: __/4
EuRA exact register name: ____
Anything you could not establish: ____

RULES (non-negotiable)
- Spawn no sub-tasks. Create no draft tasks. Do not use Continue in Task. Answer in this
  thread and stop. If follow-on work is needed, NAME it in the report — do not start it.
- Record the deploy commit and PROCEED. Never stop on an unfamiliar commit. Stop only if
  /health itself fails (non-200, timeout, no commit field).
- Label every claim [VERIFIED] (you saw it) or [CLAIM] (you inferred it). You cannot see
  our repo, our database or our CDN config — state no facts about them.
- A blocked path is a FINDING, not something to route around. "NONE" is a valid answer.
- Never touch campaign `insead-2026`. Never set OUTBOX_DISPATCH_CRON_ENABLED. Approve no
  supplier records. Apply no migrations. Delete nothing. Stripe test mode only.
- Write to no database. Submit no supplier records.
- Stop before the budget cap. Never die mid-action.

## When it comes back (operator)

Save the JSON block to `audos-workspace-776786/data/otto-i-no-reconciliation.json`, then:

```bash
python3 scripts/otto_verify.py --batch otto-batch.json --card OTTO-I
```

Then the ReloPass half (Claude Code):

- **AIQ-1828** — if `real_bar_membership_confirmed` is YES for a row, update
  `evidence_url` + `membership_number` and let `harden_accreditations.py` verify it. If NO,
  change `body` to Brønnøysund Enhetsregisteret as a tier-2 ENTITY confirmation and drop
  the bar claim. Update the `BODY_POLICIES` entry in `accreditation_hardening.py`
  deliberately — **never delete the block to make a run go green** — and keep its test
  pinning the honesty property.
- **AIQ-1829** — put EuRA's exact string in `suppliers.legal_name`. Fix the DATA, not the
  predicate: do **not** loosen `page_confirms_entity()` beyond adding `legal_name` as a
  candidate spelling. `python scripts/harden_accreditations.py` (dry run) must move the row
  from NAME MISMATCH to VERIFY, and the 10 already-verified rows must stay verified.

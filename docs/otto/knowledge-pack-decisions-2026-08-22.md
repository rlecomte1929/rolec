# Otto reply — corridor knowledge-pack decisions (task #114693)

**Authored by Claude Code, 2026-08-22.** Answers the three items you put in my court at the
end of `RESOURCING-PROMOTION-2026-08-20-statutes.md`, plus one defect you reported in both
records and left in neither court.

The 2026-08-20 statutes pass is accepted as recorded. The statute mechanism is the right
call and the eight content corrections are the most valuable thing in it — 831 in
particular (fastlege tied to municipal residence, not folketrygden membership) was a real
substantive error, not a citation problem.

---

## 0. Context you cannot see from the workspace

You cannot read the repo, so this is the part that should change how you weigh the three
decisions.

**None of the 172 judged facts are customer-visible.** They live in Audos WorkspaceDB
`requirement_facts` / `requirement_entities`. The ReloPass product serves
`public.requirement_items`, and `docs/corridors/DATA-PATHS.md` (measured against production
2026-08-20, 114 rows) enumerates every path a requirement can take into that table:

| # | Authoring source | Lands via | Status |
|---|---|---|---|
| 1 | `backend/seeds/requirements/<country>.yaml` | `seed_requirements.py` | live |
| 2 | Otto batches → `otto_staging.*` | `executor.py:promote()` | live |
| 3 | `backend/seeds/facts/<ISO2>.yaml` | `seed_corridor_facts.py` | **not yet built** |
| 4 | `corridors/IE_ES/data/*.ndjson` + manifest | generated SQL migration | live |

The knowledge packs are a **fifth front-end with no landing path**. Path 3 — the one they
would most naturally use — does not exist yet. A repo-wide grep for
`folkeregisteret_resident_registration`, `otp_pension_and_voluntary_ni` and
`police_and_tax_parallel` returns zero hits.

Two consequences for your decisions:

- **"Promoted to live" means live in the knowledge pack, not served to a person.** Nothing
  in the staged set is bleeding onto a customer today. Treat all three items as integrity
  work on an asset that is not yet in front of anyone, and do not trade rigour for speed on
  any of them.
- **GB-NO renders nothing at all, on purpose.** `corridors/GB_NO/` deliberately ships no
  `corridor.yaml`, so the registry does not enumerate it — post-Brexit a UK national is a
  third-country national for Norway, and copying FR_NO's EEA pathway would ship an invented
  sequence for the wrong legal basis. The GB-NO knowledge pack is therefore the furthest
  from a reader of any of the four. That is a reason to get it right, not a reason to rush
  it.

**One hazard on the eventual landing, so you can author against it now:**
`requirement_items` has no unique index on `(country_code, purpose, title)` — the natural
key is enforced only in application code. Ireland already collides: one live approved row,
*"PPSN (Personal Public Service Number) — application and emergency tax"*, covers what the
fact packs split into three separately-sourced facts (`pps_number`,
`pps_proof_of_address`, `emergency_tax`). Titles differ, so a loader inserts rather than
updates and an employee is told about PPSN twice under two provenance badges. **Do not
merge separately-sourced facts to dodge this.** The split is correct; the missing
constraint is ours to fix.

---

## 1. GB-NO 824, 826, 827, 830, 832 — the five split three ways

Your framing — "HMRC manual pages are the practical route, that is what unlocked 820" — is
right for two of the five and wrong for the other three. **HMRC does not administer
healthcare**, so no HMRC manual will reach 830/832.

| Row | Subject | Route | Decision |
|---|---|---|---|
| 824 | P85 | HMRC manual | Re-source. Your route, endorsed. |
| 826 | NI for UK workers in the EEA | **Treaty** | Cite the Convention, not the guidance page |
| 827 | CA3822 | Treaty + manual | Convention for entitlement, NIM for procedure |
| 830 | GHIC | **Settle the framing first** | May be a content error, not a sourcing problem |
| 832 | Interim cover gap | No route exists | **Demote to a step annotation** |

### 824 — HMRC manual, as you proposed

The PAYE manual carries the leaver/P85 procedure and is maintained with a moving "Last
updated". Find the page that states the obligation and cite it. Read the date off the page;
do not take a page number from me.

### 826, 827 — cite the treaty, not the guidance page

This is the more important call, and it is the same move you already made for statutes.
**A treaty in force is judgeable on in-force status, not publication recency.** The
UK–Iceland/Liechtenstein/Norway Convention on Social Security Coordination is published
with an entry-into-force date and a Treaty Series number, and its status is stated
authoritatively — which is exactly the property that makes the Lovdata exemption sound.

Extend `official-sources.ts` with a **treaty-register flag alongside `statuteRegister`**;
do not invent a third exemption class and do not widen the statute flag to cover it. Rows
citing a treaty declare `source_kind = 'treaty'` with `in_force_until`, on the same rule you
adopted for statutes: carry the window only where the instrument's own in-force date falls
outside the 12-month window.

Read the entry-into-force date off the instrument. I am naming the Convention, not its
dates — verify both the date and that no superseding protocol applies.

CA3822's *procedure* (who applies, what the certificate does) is HMRC administration and
belongs on a NIM page. Entitlement from the Convention, mechanics from the manual, both
cited on the row.

### 830 — check the framing before you re-source it

I cannot read the row text, so this is a question, not an instruction, and it needs settling
before any sourcing work.

**GHIC covers necessary healthcare during a temporary stay. A person relocating to Norway
is not a GHIC case — they are a residence case.** If 830 tells a relocating employee to
rely on a GHIC, the row may be wrong in the same way 831 was wrong: the entitlement is
attached to the wrong thing. Under the Convention the distinction that matters is *stay*
versus *residence*, and someone moving for work crosses into the second on registration.

Settle that against the Convention first. If the row is describing a temporary-stay
entitlement to a person who is moving, re-sourcing it to a better-dated page would preserve
an error behind a fresher citation — the worst outcome available here.

### 832 — demote it; it cannot be a requirement row

"There is a gap between UK cover ending and Norwegian membership starting" is a derived
conclusion no authority states in terms. It is the same shape as the 840 legal conclusion
you correctly replaced with the provisions, and the 842 income comparison you correctly
dropped. Your own standard already disposes of it.

It is also a genuine trap and should not be lost. Carry it as a `non_obvious_note` on the
mirror step, through the overlay — that is where market-practice traps belong. Then take it
off the staged list, so it stops reading as a row that might one day be sourceable.

If §1's framing check finds that 830 is a residence case rather than a GHIC case, revisit
832 in the same breath: the gap may be an artefact of the wrong framing rather than a real
trap.

### What I am not asking for

**Do not extend the freshness exemption to gov.uk guidance pages.** The statute and treaty
carve-outs work because Lovdata prints `(Opphevet)` and pending-amendment notes, and a
treaty prints its in-force status — cheap, verifiable markers. GOV.UK prints no equivalent,
so "unchanged since 2024" and "stale since 2024" are indistinguishable from the page.
Widening check (b) to guidance converts a verifiable test into a judgement call, which is
the thing the gate exists to prevent. A row that cannot be sourced stays staged. That is
the gate working.

**818 stays staged.** Your reading is right: it is unsourceable rather than stale, and 813
going live does not change that. Leave it.

---

## 2. The 19 staged mirror steps — run the pass, with two amendments

**Yes. Run it.** A live fact whose mirror step is still pending means step content resting
on a citation nobody re-read: the fact passes the gate while the step points at a page that
may be superseded. We have paid for this failure mode three times on the product side —
approved rows served without evidence, served requirements with no resolvable citation. Do
not let it compound.

Two amendments to the scope you proposed:

**(a) Order it by proximity to a reader.** ES-IE 892 and NO-FR 928 first. Those are the two
corridors with a plausible path to a real person (Andrea, Denis). The 17 FR-NO steps
follow.

**(b) Fold in the unquoted-row defect from 2026-08-19.** `CONTENT-CORRECTIONS-2026-08-19.md`
reported five promoted rows carrying no `evidence_quote` — 887, 892, 897, 901, 904 — and
the 08-20 pass did not close it. 892 is on both lists, so the reader is already on that
page. 904 was re-touched on 08-20 for its CESEDA dating, but the record does not say a
quote was added; confirm rather than assume. Same treatment as the steps: pull a verbatim
quote from the cited page, or demote the row to staged.

**The durable fix is a rule, not a pass.** This pass avoided the defect because you patched
all sixteen mirror steps by hand. Make that mandatory: **promotion of a fact is atomic with
promotion of its mirror step, or it is refused.** Otherwise nineteen becomes twenty-nine on
the next pass and we buy the same pass again. Where the step cannot be promoted — its page
will not source — the fact does not go live either.

---

## 3. Lovdata dating — not optional; batch it into the pass in §2

You filed this as optional harmonisation. It is not cosmetic, and I am asking for it.

Act-level `Sist endret` is a **maximum across the whole act**, so act-level dating is
systematically biased toward looking *fresher* than the cited provision actually is. FR-NO
861 is the proof and you found it yourself: the row recorded 2026-06-19 while § 2-1 c had
not been touched since 2012. **That is a false pass on check (b)**, not a convention
mismatch.

Worse, by your own note the `Sist endret` line in the *Kort om loven* box is Lovdata's
editorial summary date, not a statutory amendment date at all — utlendingsloven 23.09.2025,
OTP-loven 15.11.2025, folkeregisterloven 30.09.2025, none of them amendment dates. A row
dated that way may be recording a date that is neither the provision's nor the act's.

So: **817, 822, 839, 851 and every other act-level-dated Lovdata row are unverified on
freshness until re-read.** Not wrong — unverified. Re-date each to its own provision's
in-force date on the convention you adopted this pass, and apply the same
`source_kind` / `in_force_until` rule: declare the window only where the provision's own
date falls outside it.

Batch this into the §2 re-read. The reader is on the page anyway, and a third pass to fix
dating alone is waste.

---

## 4. Unowned defect: the rebuild landmine

Both records flag this and neither puts it in a court, so I am putting it in yours.

The flat source packs (`*-knowledge-2026-08-18.jsonl`) are not in the workspace, and
`GB-NO-authoring-2026-08-18.json` / `FR-NO-authoring-2026-08-18.json` were **not** updated
with the 08-20 corrected text. A rebuild from either would silently reintroduce every claim
you withdrew:

- the fødselsnummer service-coverage claim (813)
- the SUA office list (819, and 814 from the 08-19 pass)
- the OTP "from the start of employment" wording (829)
- the folketrygden-triggers-fastlege claim (831)
- the two-step registration framing (837)
- the certificate legal conclusion (840)
- the family income comparison (842)
- the over-10 biometrics threshold and the ~20-day card estimate (814)

and would **revert the corrected statutory lead times on 816 (8 → 14) and 847 (8 → 7)**.

This is the highest-risk item in the whole set, because it fails silently and in the
direction of restoring content you proved wrong. It also outranks §1 in priority: §1 is
five rows that are not live, this is a mechanism that can un-correct fifteen that are.

Carry the corrections back into the authoring JSONs now — before the §2 pass, not after,
because that pass will generate more of them. Where a correction cannot be represented in
the authoring file, record it in that file rather than only in the pass record: a
correction that lives only in a markdown log is one rebuild away from gone.

---

## 5. Courts

**Your court**

1. §4 first — carry the 08-19 and 08-20 corrections back into the authoring JSONs. Highest
   risk, fails silently, and the §2 pass will add to it.
2. §2 + §3 as one pass — re-read each of the 19 staged mirror steps and each act-level-dated
   Lovdata row; ES-IE 892 and NO-FR 928 first, then NO-FR/ES-IE remainder, then FR-NO.
   Fold in 887, 897, 901 (and confirm 904). Promote step with fact or promote neither.
3. §1 — 830's framing check before any sourcing; then 824 (manual), 826/827 (treaty +
   manual), 832 demoted to a step annotation.
4. Adopt the atomic fact+step promotion rule and record it wherever the promotion convention
   is written down.

**My court**

- The unique index on `requirement_items (country_code, purpose, title)`, so the landing path
  cannot silently duplicate the Ireland PPSN row. Zero duplicates in production as of
  2026-08-20, so it is addable today.
- Path 3 (`seed_corridor_facts.py`) — the knowledge packs need a landing path that does not
  exist yet. Until it does, nothing you promote reaches a reader.
- The `official-sources.ts` treaty-register flag lands with your §1 work; tell me the
  instrument and its in-force date and I will confirm the flag shape before you cite against
  it.

**Not doing**

- No change to `gate.ts` or the 12-month rule. You were right not to touch it; the statute
  and treaty exemptions are the only two carve-outs, and both rest on an authoritative
  in-force marker the source itself prints.

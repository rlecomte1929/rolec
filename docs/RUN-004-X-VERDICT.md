# RUN 004-X — verdict

**Both assertions PASS. Recorded 2026-08-10 against prod.**

RUN 004-X was declared *"the final verification gating v0 launch"* on 2026-07-27
(`docs/audos-run004x-closeout-prompt.md`). Its outcome was never written down. Three attempts to
run it through a browser agent produced no verdict — the last two failed before reaching step one.

This file closes it, and the assertions are now permanent Playwright specs
(`tests/e2e/tests/run004x/`) that run on every deploy rather than an errand somebody re-runs.

## JOB A — every vetted mover is reachable (#1699) ✅

Fixture `NL_SG` @ `shortlist_ready`. Measured:

```
cards=10  hasReveal=true
"Show N more vetted providers" clicked → 10 + N reachable
```

Ten is a **display** cap with a working reveal, not the hard cap of the original defect. The
assertion is on the control and the arithmetic, not on a rendered number, because a
re-introduced cap would still render a tidy list of ten.

## JOB B — the 2nd pick per category still writes its audit row (#1696 / #1700) ✅

Fixture `FR_NO` @ `shortlist_ready`. Measured, watching the browser's own network traffic:

```
available=2  added=2  audit_writes=2
POST /api/ai/decisions → [201 accept], [201 accept]
```

The **second** pick was sent as `accept`, not `override` — which is the AIQ-1691 fix. The old
defect derived accept-vs-override from rank, so every 2nd+ pick went out as `override` with a
null reason and was correctly rejected 400, silently dropping the Art. 14 audit row.

## Two corrections to the original card, both measured

**The deploy gate was wrong.** It pinned an exact SHA and said "if it differs, STOP". That gate
went stale in **26 minutes** — prod deployed over the pinned commit while the card was being
written — and halted a run at 2/20 actions having tested nothing. `main` deploys several times an
hour, so an exact-SHA gate mostly catches its own staleness. The gate's job is attributing a
result to the code that produced it, not deciding whether to run.

**Job B's starting stage was wrong.** The card began at `roadmap_ready` and clicked through
category selection, questions and "Get recommendations". At that stage the recommendations page
renders **zero** provider cards, so a run that navigates straight there asserts nothing. The
defect lives in `handleCardToggle → logDecision`, which behaves identically whether the list was
just generated or already built, so the spec starts from a built shortlist instead.

## One thing that would have hidden all of this

The first version of both specs **skipped** when the fixture had no providers. They reported
green and skipped while asserting nothing — reproducing, inside CI, the exact two-week silence
this work existed to end. An empty fixture now **fails loudly** and names the likely cause
(`tests/e2e/tests/run004x/_fixture.ts`).

Also recorded there, because it cost time: **do not diagnose an empty picker with
`GET /api/cases/{id}/vendors`.** That endpoint returns `[]` even when the page renders ten
providers — recommendations come from `/recommendations/batch`, not the vendor directory.

## Artifacts

Every fixture is `is_test = true` (test-drive provisioning stamps it), so `scripts/e2e_purge.py`
reaps them on its normal schedule with its age guard. Campaign labels are `qa-r4x-*-<runid>`.

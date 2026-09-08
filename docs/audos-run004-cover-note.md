# Audos — RUN 004 cover note (read before Segment A)

**Paste as text. The full campaign is `RUN-004-fixture-accelerated-stress.md` — this note frames how to run it.**

---

## This is NOT RUN 003. Do not hand-walk the journey.

RUN 003 walked provision → intake → roadmap → shortlist by hand. That is what killed six sessions at 40–45/50 before they ever reached the thing under test. **We built the staged-provisioning fixture specifically to retire that.** If you start by hand-walking setup on the first segment, you'll re-inflict the exact failure this campaign exists to avoid.

**The rule that changes everything:** mint the state you need with one `curl`, then start ~2 actions from the assertion.

```bash
curl -sX POST https://api.relopass.com/api/test-drive/provision-staged \
  -H 'Content-Type: application/json' \
  -d '{"first_name":"R4a1","campaign":"qa-r4a","corridor_id":"IN_DE","stage":"shortlist_ready"}'
```

Read `employee.email` / `employee.password` (and `hr.*` where the segment needs HR) from the JSON. Sign in. You land at Review & budget with a shortlist already built. A test that was 45 actions is now ~8.

**If a segment can start from a stage, it MUST.** Hand-walking is the anti-pattern.

## What we're doing and why

The Paris→Oslo happy path is proven — re-walking it teaches nothing. RUN 004 targets the four things nobody has looked at:

- **A — the other 4 corridors.** ⭐ *Every test this whole cycle was Paris→Oslo.* Do India→Munich, London→New York, Amsterdam→Singapore, Madrid→Dubai even provision, seed, resolve currency, render a roadmap? **Start here — it's the biggest unknown.**
- **B — the RFQ HR loop.** Shipped this evening, never clicked. HR sees the picks → dispatches → supplier quotes from the inbox → quote returns. This is Q2/Q3, finally runnable.
- **C — the Stripe paywall.** 🔴 **test-mode ONLY.** Use only the on-screen test card. Never a real card, never a real payment. If a real-payment field appears with no test instructions → stop, that's the finding.
- **D — adversarial edges.** Cheap via the fixture. Includes a safety check that the fixture refuses `insead-2026`.

## The three lessons that cost runs — bake them in from action one

You banked these in your notes; here they are as a pre-flight list:

1. **Type by keyboard.** Setting a field programmatically doesn't fire the React handler — provisioning silently fails.
2. **PageDown** for inner scroll containers that ignore the wheel (Select-services, questions, recommendations).
3. **Click custom controls by coordinate, never by ref** — ref-clicks silently fail on toggles/checkboxes.
4. Country fields → use the dropdown, never type.

## Hard boundaries (unchanged, non-negotiable)

- Campaign per segment: `qa-r4a`…`qa-r4d`. **Never `insead-2026`.**
- **Stripe: test-mode only.** No real card, ever.
- **No real emails** — a hard guard blocks test personas from emailing suppliers; if a real outbound email happens, that's 🔴 critical, stop.
- Never set `OUTBOX_DISPATCH_CRON_ENABLED`. Approve no supplier records. ≤20 actions/segment. BLOCKED ≠ FAIL. Screenshot each assertion. Report every `qa-r4*` artifact.
- **A blocked path is a finding, not something to route around.** Stop before the budget cap — never die mid-action.

## Cadence

One segment per session, mint fresh each time. Run **A → B → C → D**. Report each in the standard block; Cowork runs the DB half (token minting, quote rows, `access_tier` flips, and confirming **zero Resend sends**).

**Start with Segment A, IN_DE, `stage=shortlist_ready`.** If the `curl` 404s or returns an empty shortlist for that corridor, that is itself the first finding — report it and try `GB_US`. Do not fall back to hand-walking.

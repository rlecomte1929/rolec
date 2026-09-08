# ADS-1 — questions for Audos, before any spend

**AIQ-1781.** Drafted for Romain to send to Andres Zubillaga. **Human-only task** — this is
a commercial negotiation, not an engineering step. Nothing here should be sent by an agent.

The engineering is done or in flight regardless; this gates **spend**, not build.

---

## Why this comes first

A free ad test can quietly attach a permanent revenue share, hand account ownership to a
partner, or route all conversion data through someone else's domain. Those are cheap to
settle now and expensive to unwind after a campaign is live.

---

## The confirmed problem — item 5

Audos is **already hosting a ReloPass-branded landing page on their domain**:

```
audos.com/p/d0c29613-9cb5-4652-9c6a-494eeed352e5/test-drive-access
```

It captures work email (required), company (optional), role (optional), then sends a
4-digit code. That is close to our Segment A spec — genuinely a good sign that Otto is
already thinking about qualification.

But if ads point there, three things follow:

1. **No first-party conversion data.** The OpenAI pixel and the `__oppref` cookie live on
   audos.com. We see what Otto reports and nothing independently auditable.
2. **The durable value accrues to the wrong domain.** `OAI-SearchBot` crawling that path
   builds *audos.com* citability in ChatGPT answers, not relopass.com. Being citable is
   the asset that keeps paying after the paid test ends — and this setup forfeits it
   entirely.
3. **Lead custody is unclear.** The form asks the right questions; the open question is
   who holds the resulting list.

**Position:** ads should point at `relopass.com`. At absolute minimum, the OpenAI pixel
and the lead data must sit on the ReloPass domain.

**Frame it as making the beta measurable, not as a demand.** Audos benefits from a clean
read too — a test nobody can attribute is a test that proves nothing for either side. Both
landing pages are built and prerendered on relopass.com, so pointing ads at them costs
Audos no work.

---

## Must-answer (hard gates: 1, 4, 5)

1. **Does joining the ChatGPT ads beta trigger the standard Audos revenue-share terms, or
   is it separate?**
   ReloPass is venture-track B2B. A permanent 15% revenue share is a materially different
   decision from a free ad test, and not one to make implicitly.

2. **Who owns the OpenAI ads account?** If this works, do we keep the account, the pixel
   history, and the audience data?

3. **What is the actual credit amount, and how long do we have to spend it?**

4. **Which geographies can Otto buy?** Can it buy UK and the EU, or is it US-only?
   If Otto is US-only, this test is far narrower than it looks and the budget split should
   be reconsidered before it runs.

   > **Amended 2026-08-10.** This item used to carry a second sentence — *"No EU member
   > state can be targeted"* — with no reason attached, and it propagated into the ADS-5
   > brief as policy. It was never policy. It belonged to ChatGPT ads being a US-first
   > product, i.e. the same capability question this item already asks. Left as written it
   > blocked FR→NO, our own first corridor, on a rule nobody could justify.
   >
   > **Our half is now answered: EU targeting is permitted while no third-party ad pixel is
   > installed.** The EU-specific obligation is about tags on the visitor's device
   > (ePrivacy Art. 5(3)), not about who sees an ad; no pixel exists today, ADS-4's
   > attribution is first-party and does not need one, and
   > `scripts/check_ad_pixel_consent.py` fails the build if one is added without a consent
   > gate. Reasoning in full in the ADS-5 Geography section.
   >
   > **Audos still owes the capability half** — that is the question above, and it is the
   > only part of item 4 that is still open.

5. **The domain question above.** Can ads point at relopass.com? If not, can the pixel and
   lead data still sit on our domain?

## Also worth asking

- Can we supply the context hints and exact card copy? (Both are written and ready.)
- Otto's proven engine is consumer paid social. How is it adapted for B2B software with no
  immediate purchase?
- Where do leads land — can they route to our CRM or a webhook?
- What reporting granularity, and can we export raw click and conversion data?
- Who else is in the beta cohort, and is there a shared learning channel?

---

## Rollback

Decline the beta. Nothing has been spent, and the landing pages, crawler allowlist and
attribution plumbing are ours regardless — they serve any future paid or organic channel.

## Done when

All five answers received **in writing** and saved to the workspace. Items 1, 4 and 5 are
hard gates: **do not release spend until item 5 is answered.**

# `/api/public/track` — why it runs before consent

**AIQ-1781.** Recorded 2026-08-10. Status: **decided, not reviewed by counsel.**

## The question

`emitMarketingEvent` (`frontend/src/analytics.ts`) fans out to two sinks. The PostHog half
is consent-gated — `opt_out_capturing_by_default: getAnalyticsConsent() !== 'granted'`. The
`POST /api/public/track` half **is not**, so `landing_page_view`, `landing_cta_click`,
`landing_scroll_depth` and `landing_time_on_page` are recorded for every visitor to the paid
ad landing pages, including EU visitors who have not answered the ConsentBanner.

That was noticed while resolving the ADS geography rule. It was not a deliberate choice at
the time — it fell out of the code — so this note makes it one.

## The decision: keep it ungated, and pin the assumption with a test

The first instinct was to gate it. Reading what actually reaches storage changed that answer.

`track_event` (`backend/app/routers/public_analytics.py`) allow-lists the event name, sets
`extra="forbid"` on the request model, and allow-lists the property keys down to
`utm_source`, `utm_campaign`, `utm_medium`, `utm_content`, `cta`, `source`, `page`, `depth`,
`seconds`. It then calls `emit_event(body.event, extra=safe)` — **with no `user_id`, no
`case_id`, no `request_id`, no IP, no cookie or device identifier.** The stored row is an
event name, a server timestamp, and a handful of campaign and engagement scalars.

Two consequences:

1. **ePrivacy Art. 5(3) is not engaged.** That article governs storing information on, or
   gaining access to information already stored on, a visitor's device. A plain POST to our
   own origin does neither. No cookie is set and no local storage is read on this path.
2. **There is no personal data in the payload to have a lawful basis *for*.** Nothing in the
   row distinguishes one visitor from another; it cannot be linked back to a person even in
   principle. Aggregate campaign measurement of this shape is the standard example of
   analytics that falls outside consent requirements.

Gating it would therefore have cost the campaign its only read-out — engagement per creative
angle is the only signal legible at ~50 clicks, long before conversions are dense enough to
compare — and bought no privacy in return. That is a bad trade, and it would have been made
on instinct rather than on the payload.

## What makes this durable rather than a claim in a document

The reasoning holds *only while the payload stays anonymous*. Someone adding `user_id=` or a
request id to that one call would falsify the whole note, and every existing test would still
pass — the same failure shape as ADS-4's gate G1, which read as satisfied while both landing
pages served an empty shell.

So the assumption is pinned:
`backend/tests/test_public_track.py::test_track_attaches_no_identifier_to_the_event`
asserts the call carries `extra` and nothing else, and fails by name on any identifying
kwarg.

## Scope, and what would change this

- Applies to `/api/public/track` only. The `leads` capture path is a different thing
  entirely — it collects a work email, is user-initiated, and carries its own basis.
- **If an ad pixel is ever installed**, this note does not cover it. A third-party pixel
  does store and read device information, so Art. 5(3) applies and it must sit behind the
  ConsentBanner. `scripts/check_ad_pixel_consent.py` enforces that, and the ADS geography
  rule depends on it.
- If we ever want per-visitor funnel analysis on these pages, that is a genuinely different
  processing activity and needs consent — not an extension of this note.

Related: `docs/gtm/ADS-5_otto_campaign_brief.md` (Geography), `PRIV-004_sub-processor_register.md`.

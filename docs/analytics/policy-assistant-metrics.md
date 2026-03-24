# Policy Assistant analytics — HR value and privacy

## What we record

Server-side events (via `analytics_events` / `emit_event`) on each policy assistant query:

| Event | When |
|--------|------|
| `assistant_question_asked` | Every turn (no question text) |
| `assistant_question_supported` | Classifier accepted the question as in-scope |
| `assistant_question_unsupported` | Classifier rejected (includes `refusal_code`) |
| `assistant_answer_generated` | Always after an answer is built |
| `assistant_answer_topic` | Only when `canonical_topic` is set |
| `assistant_answer_readiness` | Every turn (`comparison_readiness` + `answer_type`) |
| `assistant_refusal_shown` | Answer is a refusal with a refusal code |
| `assistant_follow_up_clicked` | Client beacon when user taps a **Related questions** chip |

Payloads are intentionally small: `user_role` (HR / employee), `request_id`, and `extra` with **enums and buckets only** — e.g. `canonical_topic`, `comparison_readiness`, `policy_readiness_bucket`, `message_length_bucket`, `refusal_code`. We **do not** store raw user messages, policy excerpts, or assignment/policy UUIDs in these events (assignment id is omitted from assistant payloads).

## Summary metrics (how to compute)

Using `analytics_events` for a time window:

1. **Top policy topics** — Count `assistant_answer_topic` grouped by `payload.extra.canonical_topic` (filter `user_role` = `employee` vs `HR` as needed).

2. **Unsupported rate** — `assistant_question_unsupported / assistant_question_asked`, or use admin `GET /api/admin/workflow/overview` field `rates.assistant_unsupported_rate_pct`.

3. **% questions resolved from published policy** — Share of turns where `assistant_answer_generated` has `answer_type` in `entitlement_summary`, `comparison_summary`, `status_summary`, `draft_published_summary` (HR) and **not** `refusal` / `clarification_needed`, scoped to `policy_readiness_bucket` = published-ready buckets for employees.

4. **% informational-only answers** — Among substantive answers, share where `assistant_answer_readiness` has `comparison_readiness` = `informational_only` or `external_reference_partial` (tune to your product definition).

5. **Likely repetitive HR question areas** — For `user_role` = `HR`, group `assistant_answer_topic` or `assistant_question_supported.extra.detected_intent` with high volume; cross-check `policy_readiness_bucket` = `draft_with_published` to spot draft-vs-published friction.

## Demonstrating HR time saved

- **Deflection before ticket**: Rising `assistant_question_asked` for employees with stable HR case volume suggests self-serve policy clarification.
- **Lower unsupported over time** (with stable traffic) suggests clearer policies or UX.
- **High follow-up click rate** (`assistant_follow_up_clicked` / `assistant_answer_generated`) indicates users are staying inside guided flows rather than retyping.
- **HR concentration on `draft_with_published`** plus topic clusters highlights where HR spends cognitive load before publish — good targets for docs or product copy.

This is **directional** evidence; pair with HR interviews or ticket tags for a full story.

# Policy Assistant analytics — HR value & privacy

## What we collect

Events are emitted via `emit_event` → optional `analytics_events` row (`event_name` + JSON `payload_json`). **We do not store question text**, assignment/policy IDs, or user IDs in policy-assistant payloads. Correlating fields:

- `request_id` — per HTTP request (or per assistant turn where returned to the client).
- `user_role` — `HR` or `employee`.
- `extra.*` — bounded enums/buckets only (topics, readiness, refusal codes, intent, answer shape).

Event names (see `backend/services/policy_assistant_analytics.py`):

| Event | Purpose |
|-------|---------|
| `assistant_question_asked` | One row per turn; includes length bucket, policy readiness bucket, comparison readiness, topic/intent when known. |
| `assistant_question_supported` / `assistant_question_unsupported` | Classifier outcome. |
| `assistant_answer_generated` | Answer shape + `answer_value_bucket` + `policy_grounding_bucket` + `resolved_from_published`. |
| `assistant_answer_topic` | Topic-attributed answers (for “top topics”). |
| `assistant_answer_readiness` | Comparison readiness × answer type (for informational-only rate). |
| `assistant_refusal_shown` | Refusal surfaced to user. |
| `assistant_follow_up_clicked` | Client beacon; optional `assistant_turn_request_id` links to the query `request_id` that showed the chip. |

## Summary metrics (example definitions)

Use `payload_json` as JSON (SQLite: `json_extract`, Postgres: `payload::jsonb`). Paths assume `emit_event` shape: top-level `user_role`, nested `extra` for assistant fields.

1. **Top policy topics** — Count `assistant_answer_topic` grouped by `extra.canonical_topic` (filter `user_role = 'HR'` or `'employee'` as needed).

2. **Unsupported rate** —  
   `assistant_question_unsupported / assistant_question_asked` over a time window (same role filter).

3. **% questions “resolved” from published policy** — Share of `assistant_answer_generated` where `extra.resolved_from_published = true` (strict: published grounding only). For HR, also report `policy_grounding_bucket` mix (`published` / `draft` / `mixed`).

4. **% informational-only answers** — Share of `assistant_answer_generated` where `extra.answer_value_bucket = 'informational_only'` (add `partial_numeric` / `review_required` if you want a broader “non-comparison-ready” band).

5. **Likely repetitive HR question areas** — For `user_role = 'HR'`, group `assistant_answer_topic` by `canonical_topic` and rank; optionally weight by `assistant_follow_up_clicked` on the same `canonical_topic` to see which topics drive follow-up churn.

## How this demonstrates HR time saved (narrative)

- **High** `resolved_from_published` + **low** unsupported rate → employees and HR are getting grounded answers without escalation.
- **Top topics** + **follow-up clicks** → shows where policy language is unclear or where HR repeatedly clarifies the same benefit (prioritize doc or UI improvements).
- **Informational-only / partial_numeric** share → quantifies how often the assistant correctly refuses invented dollar comparisons—reducing bad self-service answers without claiming false precision.

## Privacy

- No raw messages, no PII in `extra`.  
- Do not join `request_id` to PII in reporting unless your data governance explicitly allows it.  
- `assistant_turn_request_id` on the beacon is only for correlating a click to a prior assistant response, not for identifying users.

# Engine routing — deterministic policy assistant (2026-05-07)

Replaces the missing `docs/eval/2026-05-06-engine-routing.md` referenced
by the eval spec. Captures only what was verified read-only against
production this session; everything else is left for a follow-up.

## Engine under test

Eval target is the **deterministic** policy assistant endpoint:

- `POST /api/hr/policy-assistant/query` — defined at
  [main.py:7555](backend/main.py#L7555); response built by
  [hr_policy_assistant_service.py:320](backend/services/hr_policy_assistant_service.py#L320)
  via `execute_hr_policy_assistant_query`, which composes
  `classify_with_bounded_session` + `generate_policy_assistant_answer`.
  No LLM in the path.

Do **not** target the LLM-orchestrated RAG path:

- `POST /api/policy-assistant/rag-query` — defined at
  [main.py:7605](backend/main.py#L7605). It calls
  `policy_assistant_rag_engine.answer_policy_question`. Out of scope
  for this eval line.

The employee-facing twin is `POST /api/employee/policy-assistant/query`
([main.py:7521](backend/main.py#L7521)). Not used here because the
eval is HR-scoped.

### Request shape

`HrPolicyAssistantQueryRequest` ([main.py:1172](backend/main.py#L1172)):

```
{ "policy_id": "<uuid>",            // required
  "message": "<question>",          // required, <= 8000 chars
  "document_id": "<uuid> | null",   // optional
  "session": { ... } | null }       // optional, bounded session state
```

`policy_id` is mandatory — the engine refuses with HTTP 400 otherwise.
`message` is mandatory and length-capped server-side.

### Response shape

`PolicyAssistantAnswer` ([policy_assistant_contract.py:217](backend/services/policy_assistant_contract.py#L217)),
wrapped by the route as:

```
{ "ok": true,
  "policy_id": "...",
  "document_id": null,
  "request_id": "...",
  "answer": { /* PolicyAssistantAnswer */ },
  "session": { ... } }
```

`answer.answer_type` is one of `entitlement_summary | comparison_summary |
status_summary | draft_published_summary | clarification_needed | refusal`
([contract.py:93](backend/services/policy_assistant_contract.py#L93)).
On refusal, `answer.refusal.refusal_code` is one of the enum values listed
in **Refusal taxonomy** below.

## Auth path

- Login: `POST /api/auth/login` with HReval credentials. PBKDF2 path
  via `public.users` (per spec; not re-verified this session).
- Returned token used as `Authorization: Bearer <token>` on all subsequent
  REST calls. Confirmed working against `https://api.relopass.com`
  this session: `GET /api/hr/policies` returned 200 in ~1.1s.
- Token in this session was a UUID-shaped value, not a JWT — consistent
  with a session-token model rather than a self-contained JWT. Future
  evals should not assume JWT semantics (e.g. don't try to decode claims
  client-side).
- Do **not** initialize the Supabase client SDK with this token; REST
  only.

## Refusal taxonomy (in-repo, authoritative)

`PolicyAssistantRefusalCode` from
[policy_assistant_contract.py:137](backend/services/policy_assistant_contract.py#L137):

```
out_of_scope_general
out_of_scope_legal_tax_immigration_travel       (legacy umbrella)
out_of_scope_legal_advice
out_of_scope_tax_beyond_policy
out_of_scope_immigration_beyond_policy
out_of_scope_negotiation
out_of_scope_school_or_neighborhood_advice
out_of_scope_travel_or_lifestyle
out_of_scope_unrelated_chat
no_published_policy_employee
no_policy_context
ambiguous_or_ungrounded
role_forbidden_draft
insufficient_policy_data
```

Refusal copy is centralised in
[policy_assistant_refusal_service.py:76](backend/services/policy_assistant_refusal_service.py#L76)
(`_refusal_prefix`).

There is **no** `POLICY_GAP` or `EXTERNAL_TABLE` enum value. The eval
spec's two not-covered conceptual categories both collapse to
`insufficient_policy_data` in the current contract. Comparison-readiness
has an `external_reference_partial` value
([contract.py:126](backend/services/policy_assistant_contract.py#L126)),
but it lives on `comparison_readiness`, not on `refusal_code`, and is
emitted on substantive answers, not refusals. A future eval that wants
to distinguish "topic absent" from "topic mentioned but value external"
will have to do so via the refusal text + evidence shape, not the enum.

## Endpoint path corrections

The original eval spec named two endpoints that do not exist as backend
routes:

| Spec name                     | Status                  | Real route                                                     |
| ----------------------------- | ----------------------- | -------------------------------------------------------------- |
| `GET /api/hr/policy-config`   | 404 — does not exist    | none; closest is `GET /api/hr/policies/{policy_id}`            |
| `GET /api/hr/company-policies`| 404 — does not exist    | `GET /api/hr/policies` (list)                                  |
| `GET /api/hr/policy-documents`| Exists but **hangs 20s+** | same path; see "Production reliability finding"              |

`grep -nE '@app\.(get\|post)\("/api/hr/' backend/main.py` enumerates
the real surface. Future eval specs should be drafted against that.

## Production reliability finding

`GET https://api.relopass.com/api/hr/policy-documents` with a valid
HR bearer token returned **0 bytes after 20.0s** before the client
aborted. This matches the 15s cancellation the UI shows in the browser.
Recording here as the second occurrence on the same day; not investigated
this session per scope. Per the eval spec's HARD_FAIL rule for
production timeouts that prevent an answer, any future eval that needs
to read documents through this endpoint should treat this as a blocking
HARD_FAIL finding rather than a transient.

## What a future eval session should do

1. Resolve the tenant-binding question first (see
   [2026-05-07-baseline-deterministic.md](docs/eval/2026-05-07-baseline-deterministic.md)).
   The HReval token in this session resolved to the seeded demo
   tenant, not `eval_synth_2026_05`. Without a token bound to the
   right company — or a documented company-switcher header — the eval
   cannot reach the Standard baseline.
2. Once a tenant-correct `policy_id` is in hand, hit
   `POST /api/hr/policy-assistant/query` directly with that
   `policy_id`. No call to `/api/admin/*`, no DB writes, REST only.
3. Treat `insufficient_policy_data` as the expected refusal_code for
   both conceptual POLICY_GAP and EXTERNAL_TABLE buckets, and call out
   the collapse as a contract observation.
4. Do not retry the `/api/hr/policy-documents` hang; baseline content
   can be read via `GET /api/hr/policies/{policy_id}` (verified shape
   in this session).

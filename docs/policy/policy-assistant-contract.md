# ReloPass policy assistant — backend contract

The **bounded policy assistant** answers questions **only** from **validated company relocation policy data** for the relevant **company / assignment / case**. It is **not** a general chatbot.

## Availability

- **Employee profile**: published policy for that employee’s assignment context.
- **HR profile**: same, plus **draft / working version** surfaces where the product already exposes them (e.g. normalization draft, grouped review).

## Product rules

1. **In scope**: Entitlements, limits, applicability, published vs under-review status, and **in-product** comparison readiness — **as grounded in ReloPass policy payloads** (published matrix, exclusions, conditions, draft rows when role allows).
2. **Out of scope (must refuse)**: General **legal**, **tax**, **immigration**, **travel**, **lifestyle**, medical, schooling choices, vendor recommendations, other companies, other employees’ data, speculation without policy text.
3. **No fabrication**: `answer_text` and `evidence` must not invent caps, currencies, jurisdictions, or legal conclusions not present in source data.

## Implementation artifacts (Python)

| Artifact | Location |
|----------|----------|
| Intents | `PolicyAssistantIntent` in `backend/services/policy_assistant_contract.py` |
| Canonical topics | `PolicyAssistantCanonicalTopic` (+ `POLICY_ASSISTANT_TOPIC_ORDER`) |
| Answer envelope | `PolicyAssistantAnswer` |
| Refusal | `PolicyAssistantRefusal` + `PolicyAssistantRefusalCode` |
| Evidence / conditions / follow-ups | `PolicyAssistantEvidenceItem`, `PolicyAssistantConditionItem`, `PolicyAssistantFollowUpOption` |
| Role constants | `EMPLOYEE_POLICY_ASSISTANT_RULES`, `HR_POLICY_ASSISTANT_RULES` |

## Intents (`PolicyAssistantIntent`)

| Value | Use |
|-------|-----|
| `policy_entitlement_question` | What is covered / capped for a topic |
| `policy_comparison_question` | Comparison within allowed, grounded surfaces |
| `policy_status_question` | Published / review / visibility |
| `draft_vs_published_question` | HR: draft vs published (employee → refuse or redirect) |
| `unsupported_question` | Clearly off-topic |
| `ambiguous_question` | Needs disambiguation inside policy scope |

## Canonical topics (`PolicyAssistantCanonicalTopic`)

Starter set (extend only with product + taxonomy review):

`temporary_housing`, `home_search`, `shipment`, `school_search`, `spouse_support`, `visa_support`, `work_permit_support`, `tax_briefing`, `tax_return_support`, `home_leave`, `relocation_allowance`, `host_housing`

## Response schema (`PolicyAssistantAnswer`)

| Field | Purpose |
|-------|---------|
| `answer_type` | `PolicyAssistantAnswerType` — shape of the turn |
| `canonical_topic` | Primary topic when applicable |
| `answer_text` | Grounded narrative (may be empty if `refusal` is primary) |
| `policy_status` | `published` / `draft` / `draft_and_published` / `no_policy_bound` / `unknown` |
| `comparison_readiness` | Aligns with grouped comparison readiness where relevant |
| `evidence[]` | Snippets / internal references backing the answer |
| `conditions[]` | Applicability in plain language |
| `approval_required` | Policy indicates approval / exception path |
| `follow_up_options[]` | Bounded, in-scope suggested next questions |
| `refusal` | Structured refusal when not answering substantively |
| `role_scope` | `employee` or `hr` — **server-enforced**; client cannot escalate |
| `detected_intent` | Optional classifier output for UI/telemetry |

## Refusal schema (`PolicyAssistantRefusal`)

| Field | Purpose |
|-------|---------|
| `refusal_code` | `PolicyAssistantRefusalCode` |
| `refusal_text` | Safe explanation for the user |
| `supported_examples[]` | Example **in-scope** questions |

## Role scoping

### Employee

- **Sources**: **Published** policy version / benefit matrix for the bound case only.
- **Forbidden**: Draft normalization detail, unpublished limits as authoritative, other employees, off-topic domains.
- **Typical refusal**: `no_published_policy_employee`, `role_forbidden_draft`, `out_of_scope_*`.

### HR

- **Sources**: Published + **draft / working** artifacts the API already returns for that company/version (e.g. HR policy review payload slices).
- **Forbidden**: Answering as if ReloPass were a general advisor; mixing other companies; ungrounded answers.
- **Draft vs published**: Allowed intent `draft_vs_published_question` with grounded diff/status only.

## API shape (suggested, not implemented here)

Future endpoint(s) should accept at minimum: `role`, `company_id` / `policy_id` / `assignment_id` (as applicable), `message`, optional `conversation_id`, and return `PolicyAssistantAnswer` JSON **validated** against this schema.

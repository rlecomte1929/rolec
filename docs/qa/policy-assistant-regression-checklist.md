# Policy Assistant — regression checklist

**Full scenarios & red-team notes:** [policy-assistant-qa-pack.md](./policy-assistant-qa-pack.md)

## Run automated regression

```bash
./venv/bin/python -m pytest backend/tests/test_policy_assistant_qa_regression.py -v
```

**Related:** `test_policy_assistant_classifier.py`, `test_policy_assistant_refusal_service.py`, `test_policy_assistant_session_service.py`, `test_*_policy_assistant_service.py`, `test_policy_assistant_analytics.py`

## Test ↔ scenario map

| Test | Area |
|------|------|
| `test_01_*` | In-scope employee entitlement |
| `test_02_*` | In-scope HR draft-grounded entitlement |
| `test_03_*` | Legal / personal tax / immigration lawyer refusals |
| `test_04_*` | Mixed policy + travel (recovery + guardrail) |
| `test_04b_*` | Mixed negotiation (no recovery) |
| `test_05_*` | Jailbreak phrases |
| `test_06_*` | Empty message; housing disambiguation |
| `test_07_*` | No published policy (employee) |
| `test_08_*` | Informational when rule readiness missing |
| `test_09_*` / `test_09b_*` | Draft vs published: employee refusal + HR classifier + HR pipeline |
| `test_10_*` | HR strategy refusal |
| `test_11_*` | Rule-level partial readiness (no invented comparison) |
| `test_12_*` | Version-level partial matrix + topicless comparison answer |
| `test_13_*` | Visa support in-scope vs visa choice refused |
| `test_14_*` | Jailbreak + policy in one message → full refusal |
| `test_15_*` | Vague “benefits” → ambiguous |
| `test_16_*` | Tax **briefing** in-policy vs personal tax |

## Manual smoke (when changing classifier/guardrails)

1. One happy-path employee + one HR question in UI.  
2. One refusal (e.g. hotels) + one jailbreak string.  
3. Employee asks draft/publish → refusal; HR same → summary.

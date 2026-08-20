# Case Verification Report — IE→ES

**Status: NOT STARTED.** This is the template. IE→ES has no completed CVR, which is why the
corridor's 25 requirements remain `review_status='pending'` and unserved.

A CVR is a real-user session walked end to end. Its output is two things at once: the
evidence that lets a corridor's requirements be approved, and labelled training data for the
future v1 model. A corridor without one is authored, not verified.

---

## Session

| | |
|---|---|
| CVR id | `<slug>-ie-es` (ES→IE's is `andrea-es-ie`) |
| Participant | role, nationality, family shape, employer |
| Actual move | origin city → destination city, dates |
| Session date | |
| Conducted by | |
| Lawyer reviewer | name, and which records they signed off |

## 1. Requirements the user did NOT already know

**This is the moat metric.** For each of the 15 `non_obvious` records, record the user's
answer before showing them the note.

| topic_key | knew it? | reaction / quote |
|---|---|---|
| `registration_certificado_registro_ue` | | |
| `registration_nie_number` | | |
| `registration_cita_previa_bottleneck` | | |
| `registration_tie_only_for_non_eu` | | |
| `empadronamiento_dependency_chain` | | |
| `tax_residency_183_days` | | |
| `tax_beckham_regime` | | |
| `tax_ie_es_double_taxation` | | |
| `social_security_a1_posted_worker` | | |
| `social_security_nuss_afiliacion` | | |
| `healthcare_tsi_requirements` | | |
| `healthcare_ehic_transition` | | |
| `housing_fianza_regional_deposit` | | |
| `housing_nie_needed_to_rent` | | |
| `driving_dgt_registration` | | |

**Non-obvious hit rate:** ___ / 15.

## 2. Requirements we got wrong

Anything the user's lived experience contradicts. **Record these even when they are
embarrassing** — a corridor whose CVR found nothing wrong usually means the session was too
shallow, not that the data was perfect.

| topic_key | what we said | what actually happened | action |
|---|---|---|---|

## 3. Requirements we MISSED

Steps the user hit that no record covers. These become new candidates and are the most
valuable output of the session.

| what happened | domain | source found | candidate topic_key |
|---|---|---|---|

## 4. Sequence check

Did the modelled dependencies hold in reality?

- [ ] padrón was genuinely required before the Extranjería appointment
- [ ] a NIE was genuinely required before a landlord would sign
- [ ] the cita previa queue was the critical path
- [ ] the Beckham 6-month window ran from Social Security alta as described

## 5. Lawyer sign-off

The two treaty records **cannot be approved without this**. Both claim something about the
Ireland–Spain treaty tie-breaker while citing the AEAT residency page.

| topic_key | counsel verdict | correct source | approved? |
|---|---|---|---|
| `tax_residency_183_days` | | | |
| `tax_ie_es_double_taxation` | | | |

## 6. Relief moment

The `relief_moment_response` PostHog event for this session — and confirmation that
`corridor` came through as `IE-ES` rather than hardcoded to another corridor. That check is
still open for this corridor.

| | |
|---|---|
| Response (Yes/No) | |
| "What surprised you most?" | |
| Event verified in PostHog | |

## 7. Outcome

- [ ] Records approved (`review_status` → `approved`) — list which
- [ ] Records held back — list which, and why
- [ ] New candidates raised
- [ ] Corridor readiness: authored → **verified**

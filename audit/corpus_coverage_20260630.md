# Immigration corpus coverage report

- Generated: `2026-06-30T07:04:13.239230+00:00`
- Mode: **offline**
- Corridors: **8 covered** / **6 generic-seed** of 14 known

> READ-ONLY diagnostic. No synthetic immigration rules are added to the corpus. Uncovered corridors render a generic deterministic seed roadmap (RULE_NOT_FOUND), not corridor-specific authoritative guidance.

## Per-corridor coverage

| Corridor | Status | Chunks | In registry | Pathway types |
| --- | --- | ---: | :---: | --- |
| `BR_PT` | ✅ covered (corridor-specific roadmap) | 33 | no | cplp_residence, d2_visa, d7_visa |
| `CA_DE` | ✅ covered (corridor-specific roadmap) | 19 | no | blue_card, skilled_worker |
| `DE_NO` | ⚠️ generic seed (needs content) | 0 | yes | — |
| `ES_NL` | ⚠️ generic seed (needs content) | 0 | yes | — |
| `FR_CH` | ⚠️ generic seed (needs content) | 0 | yes | — |
| `FR_DE` | ⚠️ generic seed (needs content) | 0 | yes | — |
| `FR_ES` | ⚠️ generic seed (needs content) | 0 | yes | — |
| `FR_NL` | ⚠️ generic seed (needs content) | 0 | yes | — |
| `FR_NO` | ✅ covered (corridor-specific roadmap) | 24 | yes | eu_free_movement, family_reunification |
| `IN_DE` | ✅ covered (corridor-specific roadmap) | 38 | yes | blue_card, skilled_worker |
| `UK_DE` | ✅ covered (corridor-specific roadmap) | 22 | no | blue_card, skilled_worker |
| `UK_FR` | ✅ covered (corridor-specific roadmap) | 19 | no | long_stay_visa, passeport_talent |
| `US_FR` | ✅ covered (corridor-specific roadmap) | 38 | no | long_stay_visa, passeport_talent |
| `US_NL` | ✅ covered (corridor-specific roadmap) | 11 | no | eu_blue_card, highly_skilled_migrant |

## Configured corridors needing authoritative content

These corridors are configured in the corridor registry but have no corpus content, so they render the **generic seed**. They are the priority list for sourcing authoritative immigration rules:

- `DE_NO`
- `ES_NL`
- `FR_CH`
- `FR_DE`
- `FR_ES`
- `FR_NL`

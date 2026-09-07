# hk-resource-2026-09-08 — re-source clearing a held fact

**Clears:** punch-list hold *"Hong Kong — HKID 'within 30 days of arrival' for adult new arrivals"*
(the rule lives in the Registration of Persons Regulations, Cap. 177A, not the originally-fetched
GovHK page).

**Landed:** HONG KONG · IDENTITY · 1 `requirement_item`, `review_status='pending'` (append-only).

## Fact
- key: `HK:identity:hkid_30_days`
- title: Register for a HKID within 30 days of arrival
- pillar / nationality: IDENTITY / non-EEA
- source: https://www.elegislation.gov.hk/hk/cap177A — Reg. 3(1)(a)
- quote: "within 30 days of his entering Hong Kong"

## Verification
`confirm_quotes.py` → REVIEW_BROWSER (0.143 bigram — elegislation.gov.hk is a JS SPA, so the
referee's HTTP fetch got a thin shell, not the statute). **Applier-verified in a browser**:
navigated to Cap. 177A, rendered the SPA, and read Reg. 3 *"Duty to register and apply for an
identity card"* subreg. (1)(a) — the quote is present verbatim. This is the SINALEVI-style
browser grounding used for JS-SPA legislation sites, not a landing on a researcher's say-so.

## Append-only
approved count unchanged (325), expert_verified 0, nationality scope guard green.

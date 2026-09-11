# Counsel attestation — draft request for the flagged tax rows (2026-09-11)

Companion to [`README.md`](./README.md) (the conversion queue). Those 4 rows carry
`needs_lawyer_review:true`, so the admin-approve path is blocked
(`lawyer_review_gate.blocks_approval`) until counsel signs. This drafts that attestation.

**Nothing here is sent.** The real `CorridorAttestationRequest` is minted through the admin
endpoint (it generates a one-time token + a content-snapshot hash that must not be
hand-forged). This document gives you (a) the exact create parameters and (b) the
counsel-facing brief to hand the lawyer.

## TL;DR — only 2 of the 4 are attestation-ready

| Rows | Verdict | Why |
|---|---|---|
| **2× FRANCE / employment** (`5ee81624…`, `a3a69a5a…`) | ✅ **Attest now** | corpus-grounded, nationality-scoped (`OWN_NATIONAL, EU_EEA`), official sources, genuine determinations |
| **2× SPAIN / employment** (`ES:IE-ES:tax_residency_183_days`, `…:tax_ie_es_double_taxation`) | ⛔ **Hold — do not attest** | citation mismatch (see below) + `representative` tier + `nat=null` (unscoped) + wrong-direction/non-priority |

## How the attestation flow works (the two-key rule)

```
create_attestation → status="draft"        (admin; mints one-time token + content snapshot)
   → /send            → status="sent"       (opens the reviewer link, shown ONCE)
   → counsel opens https://relopass.com/attest/<token>, reviews each item,
     signs (promotion_policy="manual" ⇒ signing writes a SIGNATURE ONLY — it does not publish)
   → admin /promote   → attestation_status="attested"
        AND (because advance_review_status=true) review_status: pending → approved
   → row now clears the lawyer gate and serves.
```

Two keys, deliberately: counsel's signature and the admin's promote are separate actions
(`promotion_policy="manual"`). Signing never auto-publishes.

## Request 1 — FRANCE / employment  ✅ READY

Create via **Admin → Attestations → New**, or `POST /api/admin/attestations` (require_admin):

```json
{
  "country_code": "FRANCE",
  "purpose": "employment",
  "advance_review_status": true,
  "promotion_policy": "manual",
  "requirement_item_ids": [
    "5ee81624-a21e-5cf7-900e-3d3a70447420",
    "a3a69a5a-a09e-5f4b-9043-06e195e76d40"
  ],
  "title": "France (Denis NO→FR) — employment tax transition: counsel attestation",
  "reviewer_org":   "<tax counsel firm>",
  "reviewer_name":  "<lawyer name>",
  "reviewer_email": "<lawyer email>",
  "reviewer_credential": "Avocat fiscaliste (FR), coordinating Norwegian tax counsel",
  "ttl_days": 30
}
```

- `advance_review_status: true` is **required** — both rows are `review_status='pending'`, and
  without it the snapshot only shows `approved` rows (nothing to attest → 422). The flag also
  lets `/promote` advance `review_status` pending→approved.
- `requirement_item_ids` scopes the request to exactly these two rows (an explicit id list is
  not pillar-trimmed). The other 25 France rows are unflagged and go through the normal
  admin-approve path — they don't belong in a counsel attestation.
- Reviewer fields left as placeholders on purpose — fill in the actual counsel (do not invent).

## Counsel brief (hand this to the lawyer)

> **Scope:** the general legal requirements of the France arrival corridor for a French
> national relocating from Norway (EEA free-mover; nationality scope `OWN_NATIONAL + EU_EEA`).
> Two open cross-border tax questions span **both** French and Norwegian law — please involve
> Norwegian tax counsel. **These are open determinations:** resolve each via *"propose
> amendment"* (supply the answer), not a plain sign-off.

### Item 1 — FR-NO treaty Art. 15 allocation of Norwegian employment income (`5ee81624…`)
- **Claim under review:** The France–Norway income and capital tax convention (signed
  19 Dec 1980), Art. 15 on income from employment. Standard OECD-model rule allocates taxation
  to the residence state (France) unless (a) >183 days present in the source state (Norway) in a
  12-month period, or (b) remuneration paid by/for an employer resident in the source state AND
  (c) borne by a permanent establishment there.
- **Source:** `bofip.impots.gouv.fr` — BOI-INT-CVB-NOR-20120912 (Direction générale des Finances publiques).
- **Determination requested:** (i) whether the Norwegian employer's payroll is remuneration
  "borne by" a Norwegian establishment; (ii) how the 183-day count runs across the transition
  window; (iii) whether France applies the **credit or exemption** method to any Norwegian-source portion.

### Item 2 — Norwegian source-taxation of France-performed work (`a3a69a5a…`)
- **Claim under review:** Once the person ceases Norwegian tax residence (Skatteloven §2-1(3)
  3-year look-back), Norway retains limited source-taxation rights over Norwegian-source income.
  Open question: does income paid by a Norwegian employer for remote work **physically performed
  in France** constitute Norwegian-source income subject to Norwegian withholding (kildeskatt), or
  does performance in France break the Norwegian source nexus?
- **Source:** `skatteetaten.no` — limited tax liability on moving from Norway.
- **Determination requested:** whether Norwegian PAYE (kildeskatt) withholding should **cease
  immediately** on the move or **continue during a transition period**; treaty override under
  FR-NO Art. 15 to be analysed alongside Norwegian domestic law.

### Disclaimer counsel signs (disclaimer_version `v1`, verbatim from the platform)
> "By signing, I confirm that I am a qualified legal professional acting in my professional
> capacity and have reviewed the legal-compliance requirements listed for this relocation
> corridor. I attest that, to the best of my professional knowledge, the requirements marked
> approved accurately reflect the applicable law as of the date of signing. This attestation
> concerns the general legal requirements of the corridor only and is not legal advice in
> respect of any individual relocating person or case. ReloPass may rely on and retain this
> attestation as evidence of professional review."

### After counsel responds
Both rows are currently phrased as **open questions** ("unresolved questions that turn on…",
"The open question is whether…") ending "counsel must advise." As written they are research
memos, not servable requirement statements. Counsel's answer (the `proposed_amendment`) becomes
the definite requirement text; an admin applies the amendment, promotes (attests), and only then
approves. Do not approve the current question-phrased text.

## The 2 SPAIN rows — HOLD, do not attest

`ES:IE-ES:tax_residency_183_days` and `ES:IE-ES:tax_ie_es_double_taxation`. Three defects make
them unfit to put in front of counsel now:

1. **Citation mismatch (disqualifying).** Their own stored `review_reason` reads: *"Claim
   concerns the Ireland–Spain double taxation treaty tie-breaker but is sourced to the AEAT
   residency page, not the treaty text."* The cited source does not support the claim — attesting
   it asks a lawyer to sign off a mis-cited statement.
2. **`representative` tier + `applies_to_nationality_classes_json = null`** — unscoped, violating
   the two-record (EEA / non-EEA) rule; lower verification tier than the FR pair.
3. **Wrong direction + non-priority.** Both are `ES:IE-ES:*` (Spain-as-**destination**, i.e. an
   IE→ES arrival), not Andrea's Spain-**exit**, and IE→ES is not a demo corridor.

**Remediation before they could ever be attested:** re-source to the actual Ireland–Spain DTC
text (or the correct AEAT double-taxation page), split into two nationality-scoped records, and
raise the tier — and only then, and only if IE→ES becomes a served corridor. For the current four
demos they simply stay `pending`.

---

*Prepared by Claude Code as a draft for human action. No attestation request has been created or
sent; no row has been approved.*

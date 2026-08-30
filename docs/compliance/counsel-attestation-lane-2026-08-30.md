# Counsel-attestation lane — state, findings, and how to clear it (2026-08-30)

Prep for discharging the `needs_lawyer_review` facts. The attestation lane exists and is wired; the
gate works at approval time; but a scan surfaced an **attestation debt** worth acting on.

## The lane (confirmed wired)
- **Data:** `requirement_items.attestation_status` (`NULL → requested → attested → stale`) +
  `corridor_attestation_requests` / `_items` / `_signatures` (the two-key signing workflow). 0 requests
  exist today — the lane is dormant.
- **Endpoints (mounted, no 405):** `POST /api/admin/attestations` (create), `…/{id}/send`,
  `…/{id}/promote`; reviewer side `GET /api/public/attestations/{token}`, `…/items/{item_id}`,
  `…/{token}/sign`.
- **Gate:** `lawyer_review_gate.blocks_approval(attestation_status, blobs)` = *flagged AND not attested*.
  Enforced at `admin.py:287` when a reviewer sets `status='approved'`.

## Finding 1 — the gate correctly blocks the 2 new counsel facts ✅
Both Denis NO→FR COUNSEL requirements carry `needs_lawyer_review` (in `citations_json`) and return
`blocks_approval=True` — they **cannot be approved** at `/admin/countries` until attested:
- `France - COUNSEL: FR-NO treaty Art. 15 allocation of Norwegian employment income`
- `France - COUNSEL: Whether Norway source-taxes Denis's employment income for work done in France`

These are genuine cross-border tax-allocation questions; a tax lawyer's sign-off is the right gate.

## Finding 2 — 15 flagged requirements are already SERVING unattested ⚠️
A scan of all four corridors found **17** `needs_lawyer_review` requirements; **15 are
`review_status='approved'` with `attestation_status=NULL`** — i.e. reaching users without the counsel
review they were flagged for:
- **FRANCE (3):** fodselsnummer≠D-number; Norwegian employer owes URSSAF; two CPAM affiliation routes.
- **IRELAND (12):** Medical Card evidence; CSEP 9-month mobility; non-EEA immigration permission;
  EU/EEA entry docs; residence-permit-in-two-states; CSEP family reunification; dependant D-visa;
  leaving-before-registration; Spanish-residence≠Irish-entry; spouse Stamp 1G; Irish tax after
  departure (ordinary residence); resident+domiciled worldwide income.

**Why:** the gate lives at the *approval* path only; these were approved **before** the gate existed,
and the *serving* path (`public_corridor`) does not re-check it. So grandfathered flagged rows leak.
This is a should-attest debt, not a known error (the content is corpus_grounded + cited) — but it is
exactly the review the pipeline asked for, currently skipped.

## To clear it (your action — needs a real reviewer)
For each corridor/purpose batch of flagged facts:
1. **Create** an attestation request: `POST /api/admin/attestations` scoped to the country/purpose,
   snapshotting the flagged items.
2. **Send** it to a qualified reviewer (a Norway/France cross-border tax lawyer for Denis; an Irish
   immigration/tax solicitor for the IE set): `POST …/{id}/send` — generates the reviewer link token.
3. Reviewer opens `…/{token}`, reviews each item, and **signs** (`…/{token}/sign`) → items flip to
   `attestation_status='attested'`.
4. The 2 Denis rows then pass `blocks_approval` and can be approved; the 15 grandfathered rows are
   retroactively backed by counsel.

I did **not** create or send a request — that requires choosing an actual lawyer and sends on your
behalf. This doc + the gate verification is the setup; the reviewer choice and send are yours.

## Recommended follow-ups
- **Close the serving-path gap:** have the serving layer (`public_corridor` / `requirements_builder`)
  withhold or badge `needs_lawyer_review`-unattested rows, so a grandfathered approval can't leak
  again. (Deferred — it would change what 15 currently-served rows show; your call vs. attesting.)
- **Prioritise:** the FR/IE tax + immigration determinations (worldwide-income, ordinary-residence,
  two-state residence permit) are the highest-liability of the 15 to attest first.

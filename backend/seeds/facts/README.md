# Corridor fact packs

Source-controlled relocation facts with the provenance a customer-visible claim needs: the
official page, the date that page publishes about **itself**, and the sentence it actually
says. Enforced on every PR by `scripts/check_corridor_facts.py`.

## Why this exists

Twice, evidence was gathered by a human and then lost at the loading boundary.

`backend/seeds/requirements/norway.yaml`'s own header records that its source report checked
nine items *"each with an exact official quote and URL"*. That file's `citations:` key is a
bare list of URLs. `seed_requirements.py` passes them into `citations_json`;
`requirements_builder` resolves each citation against a `source_records` map and silently
drops whatever does not resolve. `20261031000000_frno_source_records.sql` measured the
result: **90 items carried citations, 27 resolved.** `20261032000000_remove_fake_evidence.sql`
found the rest of the damage — 27 rows whose visible evidence read `Stub content for <url>`,
and 6 pointing at `example.com`.

Neither loss was caught in review, because in both cases the data *looked* complete. This
format exists so a date and a quote cannot be dropped again, and the gate exists so nobody
has to notice.

## Facts are keyed by jurisdiction, not by corridor

The original knowledge packs keyed facts `CORRIDOR:entity:fact_key`. That cannot be
reconciled with a destination-keyed requirements table, because **the corridor is not what
makes a fact true — the authority that publishes it is**.

```
pack       GB-NO : housing-husleieloven-deposit-cap : husleieloven_deposit_cap
           ^^^^^  a consumer of the fact, not its owner
canonical  NO    : housing-husleieloven             : deposit_cap_6_months
           ^^     the authority that published it
```

Lovdata § 3-5 is a Norwegian fact whether the mover comes from London or Lyon. `GB-NO:…` and
`FR-NO:…` were two captures of one law; here they are **one fact** carrying both original
keys in `pack_keys`. That collapse is why 22 pack facts become 21 canonical ones.

It also gives origin-side facts an honest home. A UK statutory-residence-test obligation
binds someone *leaving* the UK; it is not a Norwegian requirement and must never become a
`requirement_items` row, whose `country_code` is the destination.

## Two files, two jobs

| File | Holds |
|---|---|
| `backend/seeds/facts/<ISO2>.yaml` | the facts, with provenance — owned by the publishing authority |
| `corridors/<CORRIDOR>/facts.yaml` | which facts that corridor cites, and in which direction |

**Direction lives on the binding, never on the fact.** `NO:…:reg_883_via_eea` is origin-side
for `NO_FR` and would be destination-side for `FR_NO`. Recording `role` on the fact would
mean duplicating it per corridor, and the copies would drift.

Only `destination_facts` become `requirement_items` rows. `origin_facts` are served through
the corridor surface.

`step_id` is optional on a binding. `corridors/FR_NO/pathways/EEA_FREEDOM_2026/v1.yaml` is a
six-step destination-only graph with no housing step and no origin phase, so three facts
there have no host step. Inventing steps to hold them would be authoring an immigration
sequence nobody verified. The gate checks any `step_id` you *do* give against the real
`step_graph`, so an invented one fails the build.

## Statuses

| Status | Meaning |
|---|---|
| `active` | provenance-complete, published by a primary authority |
| `representative` | visible, **awaiting counsel attestation** — necessary, not sufficient |
| `staged` | not rendered, not seeded, not gate-bearing; nothing promoted may depend on it |

`active` requires `classify_source() == official`. `representative` also accepts
`semi_official` — a statutory body restating a rule published elsewhere, which is exactly
why the `revenue.ie` and `citizensinformation.ie` facts are representative and not active.

**No corridor is sellable on the strength of this data**, and passing the gate does not make
one so.

## `preparation_item` is the inverse case

Four entries describe real preparation and real friction that **no authority publishes** — a
BankID cutoff, an interim health-cover gap, the Irish payslip catch-22, the French dossier
and guarantor expectation. They carry **no `source:` block at all**: absence, not a nulled
block, so there is nothing for someone to quietly fill in later.

The gate enforces the *inverse* of completeness on them. A preparation item that grows a
source is a failure, not a fix — it means a page was attached to a claim that page does not
make.

## Gotchas

**Quote ISO codes.** YAML 1.1 reads bare `NO` as boolean **false**, so `jurisdiction: NO`
silently becomes `False`. Every ISO code here is quoted; the gate rejects a pack whose
`jurisdiction` is missing, which is how this surfaced.

**Never invent a date or a quote.** If an authority publishes no date (`udi.no`,
`skatteetaten.no`, `politiet.no` all fail to), cite a dated official restatement instead.
That was decided on 2026-08-16 and the gate deliberately offers no way around it — a null
publication date on a promoted fact is a failure, not a skip.

## Working on these

```bash
python3 scripts/check_corridor_facts.py --root . --run-date 2026-08-19
python3 -m pytest -q scripts/tests/test_check_corridor_facts.py
```

`quote_sha256` is tamper-evidence over the normalised quote text — it catches a hand-edited
quote, and is stable if you re-wrap the YAML block. It cannot catch a mis-transcription at
capture time; only diffing against the source page does that.

Provenance for the current set is
`docs/runbooks/corridor-facts/promotion-runbook-2026-08-19.md`.

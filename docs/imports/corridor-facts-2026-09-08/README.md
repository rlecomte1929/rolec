# Corridor requirement-facts batch — 2026-09-08/09

Six corridor requirement-fact batches researched by Otto (Audos) overnight and captured by the
wired applier. **149 facts across all five pillars, every fact carrying a verbatim
`evidence_quote` from an official source.** These are **candidates only** — they land
`review_status='pending'`, `verification_status='corpus_grounded'`, and are served to no one until
the human lawyer/reviewer gate at `/admin/countries` approves them.

## Corridors

| batch | corridor | destination | mover type | facts | key sources |
|---|---|---|---|---|---|
| `es-ie-facts` | ES→IE | IRELAND | EU/EEA free-mover | 31 | gov.ie, revenue.ie, citizensinformation.ie |
| `fr-no-facts` | FR→NO | NORWAY | EEA free-mover (NO is EEA, not EU) | 27 | norway.no, skatteetaten, nav.no |
| `no-fr-facts` | NO→FR | FRANCE | EEA free-mover | 25 | service-public.fr, ameli.fr, cleiss.fr |
| `in-de-facts` | IN→DE | GERMANY | third-country (non-EEA) | 24 | bmi.bund.de, gesetze-im-internet.de, bzst.de, deutsche-rentenversicherung.de |
| `us-ec-facts` | US→EC | ECUADOR | third-country | 23 | gob.ec |
| `fr-sg-facts` | FR→SG | SINGAPORE | third-country | 19 | mom.gov.sg, ica.gov.sg, cpf.gov.sg |

Each fact record: `{fact_id, corridor, pillar, category, fact_text, evidence_quote, source_url, scope, verified_date}`.
Pillars per batch cover immigration, residence, tax, social_security, healthcare.

## Provenance (GCS, public-read)

Delivered to `gs://audos-images/workspace-media/d0c29613-9cb5-4652-9c6a-494eeed352e5/` and captured
+ verified (HTTP 200) 2026-09-09. `src/` in this directory is that captured copy; `SHA256SUMS` +
`verify_batch.py` prove it. Original GCS objects:

- ES→IE: `1788916710383_d4kdlj0w.ndjson` / `1788916723708_8yoiblnc.json`
- FR→NO: `1788913286460_vgprfszk.ndjson` / `1788913294690_ryboyqsc.json`
- NO→FR: `1788906818161_9ifm7acw.ndjson` / `1788906836250_lda9w6uh.json`
- IN→DE: `1788914623599_cu2kktsr.ndjson` / `1788914631087_qayqd4me.json`
- US→EC: `1788912076338_r0top4kk.ndjson` / `1788912082740_l7j5qvtu.json`
- FR→SG: `1788915933233_h5ldk9ds.ndjson` / `1788915963410_v4wky154.json`

**Count note (documented, not reconciled away):** `fr-sg` and `us-ec` manifests report
`facts_count` 18 and 22 while the NDJSON carries 19 and 23 — a +1 each. The NDJSON is
authoritative (the extra line is a real, quoted fact); `verify_batch.py` flags the discrepancy.

## Gap analysis vs prod `requirement_items` (at capture)

The three thinnest destinations get the biggest gains — this batch's whole point:

| destination | prod before | this batch | effect |
|---|---|---|---|
| ECUADOR | 6 | +23 | ~4× |
| NORWAY | 16 | +27 | ~2.5× |
| SINGAPORE | 22 | +19 | ~1.9× |
| FRANCE | 39 | +25 | moderate |
| GERMANY | 49 (42 pending) | +24 | moderate |
| IRELAND | 223 | +31 | saturated — mostly corroborating overlap |

## Documented gaps (from the manifests — omitted, never invented)

Facts Otto could not source from a working official page were left out and recorded, e.g.:
IN→DE EU Blue Card 2026 salary thresholds (make-it-in-germany.com was bot-blocked); FR→SG
IRAS-specific tax figures (IRAS mega-menu is unscrapeable); NO→FR numéro fiscal / France–Norway
treaty article specifics / A1 posted-worker detail. See each `manifests/*.json` `gaps`.

## Import (human-gated prod write)

`land_corridor_facts.py` maps each fact → a `public.requirement_items` row and lands it PENDING.

- **pillar → PILLAR:** immigration→RESIDENCE, residence→IDENTITY, tax→EMPLOYMENT,
  social_security→SOCIAL_SECURITY, healthcare→HEALTHCARE. `purpose='employment'`.
- **mover-type scoping** (hard rule): EEA corridors (ES→IE, FR→NO, NO→FR) →
  `applies_to_nationality_classes_json=["EU_EEA"]`; third-country (IN→DE, US→EC, FR→SG) →
  `["THIRD_COUNTRY"]`.
- `verification_status='corpus_grounded'`, `review_status='pending'`. `citations_json` matches the
  prod shape `[{url, topic_key, corridor, quote}]`, preserving the evidence quote.
- **Dedup by title** against existing (approved+pending) rows per country: title-Jaccard +
  containment of each existing title's tokens in the new fact. Default `--dedup-threshold 0.85`
  (conservative). Rationale: everything lands *pending*, so a missed dup is recoverable at the
  review gate but a falsely-skipped fact is silently lost — so only near-exact dups auto-skip;
  the rest land pending and the reviewer catches true dups.
- **Append-only:** the protected fingerprint (approved/verified rows) and the approved+verified
  counts must not move, or the transaction rolls back. Idempotent (`ON CONFLICT (id) DO NOTHING`).

Preview at the 0.85 default: **146 new, 3 auto-deduped, 35 "possible overlap"→pending**.

**APPLIED 2026-09-09** (`--apply`). 146 rows landed `corpus_grounded`/`pending`, scoped
`["EU_EEA"]` (Ireland/France/Norway) / `["THIRD_COUNTRY"]` (Singapore/Germany/Ecuador). Deltas:
IRELAND +30, FRANCE +25, NORWAY +27, SINGAPORE +17, GERMANY +24, ECUADOR +23. Append-only verified
— approved counts unchanged (Ireland 215, France 37, Norway 11, Singapore 22, Germany 7, Ecuador 6);
0 new `expert_verified`. Now awaiting the reviewer at `/admin/countries`; re-running `--apply` is a
no-op (idempotent on `id`).

```bash
PY=/Users/romainlecomte/Documents/GitHub/rolec/.venv311/bin/python
B=docs/imports/corridor-facts-2026-09-08
$PY $B/verify_batch.py                       # gate: hashes + counts
$PY $B/land_corridor_facts.py --preview      # read-only plan + dedup decisions
$PY $B/land_corridor_facts.py --dry-run      # BEGIN..INSERT..assert append-only..ROLLBACK
$PY $B/land_corridor_facts.py --apply         # commit (prod write — operator-run)
```

## Governance

Candidates only. Nothing here is served — `requirements_builder` returns `approved` rows. The flip
to approved/served on immigration/tax/legal content is the human lawyer gate at `/admin/countries`,
never automatic. There is no automated apply-on-merge; `--apply` is an operator action.

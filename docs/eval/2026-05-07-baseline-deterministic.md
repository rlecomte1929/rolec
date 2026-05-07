# Standard baseline deterministic eval — BLOCKED (2026-05-07)

**Status: did not run.** No verdict table; three findings prevented
the eval from starting against the intended policy. Companion file:
[2026-05-07-engine-routing.md](docs/eval/2026-05-07-engine-routing.md).

## Intended target (recap)

- Engine: `POST /api/hr/policy-assistant/query` (deterministic).
- Policy: Standard baseline created today in synthetic tenant
  `eval_synth_2026_05` (company_id `461a487b-8937-493c-8684-904862fcde7b`),
  initialised via `/api/hr/policy-documents/initialize-from-template`.
- Plan: 10 questions — 4 covered, 4 POLICY_GAP, 2 EXTERNAL_TABLE — with
  PASS / SOFT_FAIL / HARD_FAIL verdicts as defined in the spec.

## Findings that prevented the eval

### Finding 1 — HReval JWT resolves to the wrong tenant

`GET https://api.relopass.com/api/hr/policies` with the supplied
HReval bearer token returned a single policy:

```
policyId:      demo-hr-policy-001
policyName:    Global Relocation Policy (Demo)
companyEntity: NOR-INV-001
status:        published, version 1
created_at:    2026-02-21T07:47:25
```

That is the seeded demo policy, not the Standard baseline initialised
today. The HReval account on prod is bound to the demo company, not
to `eval_synth_2026_05`. The UI presumably scopes by an additional
mechanism the bare bearer token does not carry — most likely a
company-switcher header (`X-Company-Id` or similar) or a session
selection on the server side keyed off something other than the token.

Without that mechanism documented, the bearer token alone cannot reach
`policy_id` rows under `461a487b-8937-493c-8684-904862fcde7b`. Querying
the demo policy would have produced an eval against the wrong content.

### Finding 2 — `/api/hr/policy-documents` hangs

`GET https://api.relopass.com/api/hr/policy-documents` returned **0
bytes after 20.0s**, matching the 15s cancellation the UI exhibited
earlier today. Under the spec's HARD_FAIL rule for production
timeouts, this would by itself score every question that depends on
document content as a HARD_FAIL — so even with the right tenant, this
endpoint is not safe to read from until it is fixed.

Other policy reads in this session were healthy: `GET /api/hr/policies`
returned 200 in ~1.1s on the same token.

### Finding 3 — eval spec endpoint paths do not match real routes

The original spec named:

- `GET /api/hr/policy-config` — does not exist (404).
- `GET /api/hr/company-policies` — does not exist (404).

Real surface (verified):

- `GET /api/hr/policies` (list) — exists and worked.
- `GET /api/hr/policies/{policy_id}` — exists, not exercised.
- `GET /api/hr/policy-documents` — exists but hangs (Finding 2).

Corrections logged in
[2026-05-07-engine-routing.md](docs/eval/2026-05-07-engine-routing.md);
flagged here because designing the 10 questions required reading
baseline rule content, and the two specified read paths were not
real.

## Worst observation (verbatim)

This file would normally close with the assistant's exact response on
the worst failure. The eval did not run, so there is no assistant
response to quote. The worst **observed** behaviour from a dependent
production endpoint was:

> `GET /api/hr/policy-documents` — `curl: (28) Operation timed out
> after 20006 milliseconds with 0 bytes received` (HTTP 000, 20.006s).

## Recommendation for the next session

Fix the tenant-binding pipeline before retrying the eval. Concretely:

1. Document the company-switcher mechanism (header? session? URL
   prefix?) the UI uses when an HR user has access to multiple
   companies, and decide whether HReval should be granted explicit
   access to `eval_synth_2026_05` instead of relying on a switcher.
2. Verify that `GET /api/hr/policies` under that mechanism returns
   the Standard baseline `policy_id` for company
   `461a487b-8937-493c-8684-904862fcde7b`, then capture that
   `policy_id` for the eval.
3. Separately, restore `/api/hr/policy-documents`. Until then, plan
   to read baseline rule content via `GET /api/hr/policies/{policy_id}`
   only and avoid any question whose verification requires the
   documents listing.
4. Once both are resolved, re-run the 10-question eval against the
   real Standard baseline using
   [2026-05-07-engine-routing.md](docs/eval/2026-05-07-engine-routing.md)
   as the contract.

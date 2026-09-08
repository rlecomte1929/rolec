# Andrea (ES→IE) — live E2E run, 2026-08-22

*Full write-based E2E (`scripts/madrid_dublin_runner.mjs`) against `api.relopass.com`, run with your explicit approval. Production is deployed at commit `850d344b` — i.e. current `main` (all the merged PRs are live).*

---

## Score: 52% → ~71%

| | 08-20 (T18) | 08-22 (this run) |
|---|---|---|
| PASS | 28 | **40** |
| PARTIAL | 2 | 0 |
| FAIL | 24 | **14** |
| BLOCKED | — | 2 |
| Total | 54 | 56 |
| Pass rate | ~52% (AMBER) | **~71%** (40/56; 74% excluding the 2 correctly-gated BLOCKED) |

**By area:** Setup 14/14 ✅ · **Journey (roadmap) 2/2 ✅** · Documents 10/16 · Neighbourhood 4/8 · Services 6/10 · Agent 4/6.

The two things the assessment called out as the worst screens are fixed: **Setup** (register → case → assign) is fully green, and the **roadmap Journey** — which returned `phases: []` on 08-20 (the F5 failure) — now passes for both personas. The merged AIQ-1867 work is live and rendering.

## The 14 failures — and which are real

Every failure returned `HTTP 200 · 0 results` and was **identical across both personas** (EU and third-country), which is itself the tell: these aren't nationality-branch bugs, they're empty collections. They split cleanly into test-harness artifacts and genuine gaps.

### Test-harness artifacts — NOT code regressions

The runner registers a **brand-new HR company each run** ("Google Ireland", fresh id) and a fresh case. Per-company curation and case history therefore don't exist for it — so these zeros are expected, and understate Andrea's real (curated) experience:

| Check | Result | Why it's an artifact |
|---|---|---|
| SVC-2 vendors / SVC-4 suppliers | 0 | Vendor curation is **per-company**; the real "Google" (`46fc3db0`) has 29 curated Irish suppliers — this fresh test company has none |
| AGT-3 providers attachable | 0 | No providers attached to a case created seconds ago |
| AREA-2 schools | BLOCKED | Correctly gated — the test persona has no school-age dependants |

To measure Andrea's *actual* experience for these, the run would need to target her real curated case (`6ecadafe` / company `46fc3db0`), which the cold-start runner can't do.

### Genuine gaps — worth a ticket

| Check | Result | Read |
|---|---|---|
| **DOC-1** case immigration requirements | 0 items | The **public** corridor endpoint serves ~29 IE requirements (from `requirement_items`), but the **case-scoped** immigration view returns 0. The case path reads `immigration_requirements`, which still has **no `*→IE` rows** (135 rows across DE/PT/US/UK/FR only). The rich content and the case-scoped delivery aren't wired to the same source. |
| **DOC-3** fillable IE forms | 0 forms | No Irish form templates (permit/visa/PPSN) authored yet. |
| **DOC-4** immigration milestones | 0 milestones | No milestone/deadline timeline seeded for the corridor (assessment: `immigration_milestones = 0`). May also require the immigration file to be opened. |
| **AREA-3** Dublin address autocomplete | 0 results | Geocode/autocomplete returns nothing. AIQ-1882 priced the neighbourhood bands (that merged), but the address-autocomplete path is still empty — worth confirming the geocoding provider is actually enabled in prod env. |

**The single most useful finding:** the generic/public corridor content is rich (~29 requirements, live), but the **case-scoped immigration surfaces (DOC-1/3/4) are empty** because they read `immigration_requirements` / forms / milestones, which have no IE data — a wiring/content gap between the two representations, not a deployment problem. This is the same "several representations of one obligation that disagree" theme as the `requirement_items` authoring-path fragmentation in the forward plan.

## Deploy confirmation

`GET /health` → `commit: 850d344b` = current `main` HEAD. So every merged PR (the 5 Wave-1 + AIQ-1867 roadmap + AIQ-2027 VE→IE load) is deployed and serving. This closes the "merged but is it live?" question from the triage.

## Test data created in production (as approved)

The run created, under your own plus-subaddressed inbox (unique per run, timestamp `1787387053799`):

- `romain+t18hra_1787387053799@hotmail.com` (HR, persona A) + `romain+t18empa_…` (employee)
- `romain+t18hrb_1787387053799@hotmail.com` (HR, persona B) + `romain+t18empb_…` (employee)
- 2 HR cases (one per persona) with assignments, company "Google Ireland".

These are inert test rows. If you want them removed I can look for a cleanup path, but there's no self-service delete exposed to me — likely an admin/DB action on your side.

## Method & safety

- Run from the cloud sandbox (the device VM can't reach `api.relopass.com`); the runner is self-contained (`fs` + native fetch) and writes only to a gitignored `results/` dir in a scratch location — **your repo was not touched**.
- Full evidence (`t18_evidence_*.json`, ~595 KB, every request/response) is retained in the sandbox if you want any specific response body.
- run_id / timestamp: `1787387053799` (2026-08-22 08:25 UTC).

## Recommended next steps

1. **Wire the case-scoped immigration view to the IE content** (DOC-1) — decide whether `immigration_requirements` should carry ES→IE, or the case view should read the `requirement_items` corridor content the public endpoint already serves. Highest-impact of the real gaps.
2. **Author IE forms + milestones** (DOC-3/DOC-4) — or open the immigration file in the flow that seeds them.
3. **Confirm the geocoding provider is enabled in prod** (AREA-3).
4. **Re-run against Andrea's real curated case** to confirm vendors/suppliers/providers are non-zero for her (they should be, given company `46fc3db0`'s 29 suppliers).
5. **Counsel attestation of the ES→IE set** (from the live-check report) remains the actual go-live gate — 0/42 IE rows attested.

---

*Companion to the audit, forward plan, PR triage, and live-check. Write-based E2E run with explicit approval; test accounts are your own plus-subaddresses.*

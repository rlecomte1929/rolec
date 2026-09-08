# Audos — Q1-C closed · card S1 closed with it · HOLD

---

## 1. Q1-C: two results, both valuable

### AIQ-1649 verified fixed ✅

All three checks passed: origin reads **Paris**, the *"Destination city/country is missing"* gate is gone, and the flow reached **Recommendations** — the exact step Q1-B could not pass. Your finding from that run is confirmed closed in production.

### You also closed card S1 — without running it

The card you were *going* to be sent next asked: *do the nine auto-approved Norway suppliers reach a customer?*

**Your answer: no.** Recommendations returned `Movers (0)` and none of the nine appeared.

Cowork confirmed the mechanism you correctly hypothesised. `backend/app/recommendations/router.py` filters ranked items through HR's **`company_vendor_selections`** — a per-company curation layer. So `platform_vetting_status='approved'` alone is **not** sufficient to surface a supplier to a customer.

**That is the "undiscovered filter" the card said to watch for, and it is a PASS.** The exposure risk raised on Monday — nine machine-imported suppliers, auto-approved with `vetted_by=NULL` — does not reach customers. There is a real gate, in a place the code trace had not found. **S1 is closed. Do not run it.**

Your instinct to flag it as *"prima-facie evidence, S1 should confirm formally"* was right, and the DB check confirmed it.

---

## 2. The same gate is a campaign blocker — filed P1

The filter is correct. **Test-drive provisioning never populates it.**

| Test-drive companies, last 14 days | With any vendor selections |
|---|---|
| **65** | **1** (3 rows) |

So roughly 98% of test-drive tenants render an empty marketplace. Every INSEAD tester reaching Services will see `Movers (0)` and a banner telling them to wait for HR — and will report *"there are no providers"* as a verdict on the product.

**Filed P1:** test-drive provisioning seeds a published policy (`_seed_default_published_policy`) but nothing seeds `company_vendor_selections`. The fix mirrors the existing seeding pattern. The recommendations filter is explicitly **not** to be touched — it is the control that closed S1.

---

## 3. 🛑 HOLD — do not run Q2 or Q3

Both reuse an RFQ that cannot currently be created:

```
0 suppliers  →  no shortlist  →  "Request quotes" never enables  →  POST /api/rfqs unreachable
```

This is a **product-flow blocker, not a testing one**. There is no workaround, and improvising toward one would burn sessions the way the first four runs did. You stopped in exactly the right place.

**Q2 and Q3 unblock when the vendor-seeding P1 ships.** You'll be told when.

---

## 4. Something you observed in passing that nobody had filed

Your report noted: *"Estimates on this page are shown in NOK."*

That is **F12** — the currency defaulting to USD on an Oslo case, raised back in RUN 001 and never formally verified as fixed. Your observation is the first confirmation it now resolves to the destination currency. Logged.

This is the second time this run that something you flagged as an aside turned out to matter — the "Oslo" origin anomaly was what cracked AIQ-1649. **Keep recording the things that look slightly off even when they are not the card's question.**

---

## 5. Where the batch stands

| Card | Status |
|---|---|
| R1 — RFQ entry-point recon | ✅ closed |
| S2 — route auth guard | ✅ closed (code audit — PASS) |
| M1/M2/M3 — magic-link security | ✅ closed (code audit — all PASS) |
| Q1 / Q1-B / Q1-C | ✅ closed — produced 4 filed defects, all but one already merged |
| **S1 — unvetted supplier exposure** | ✅ **closed by Q1-C — PASS** |
| Q2 — supplier submits a quote | 🛑 **HOLD** — blocked on vendor seeding |
| Q3 — quote returns to requester | 🛑 **HOLD** — depends on Q2 |
| J1 / J2 — intake → roadmap → services | ⏸ needs the staged-provisioning fixture |

**Eight of eleven cards are closed.** The remaining three are blocked on two shipped-or-filed fixes, not on testing capacity.

---

## 6. Defects your runs produced this week

| Finding | Status |
|---|---|
| Country autocomplete corruption (3× repro + mechanism) | ✅ merged `466b1ab3` AIQ-1643 |
| Policy publish hang | ✅ merged `14b02998` + `d4470263` AIQ-1642 — the second commit defers RAG re-index off the publish path, the real cause of the 20–40s |
| Policy tabs contradicting | ✅ merged `378fe551` AIQ-1644 |
| `/api/cases/{id}/vendors` HTTP 500 | ✅ merged `9d3fab9b` AIQ-1646 |
| "HR owner" shows employee email | ✅ merged `ff4ea8dd` AIQ-1648 |
| Services destination gate | ✅ merged `d034299b` AIQ-1649 |
| `POST /api/hr/rfq-requests` orphaned | 📋 filed P2 — wire or retire decision pending |
| Test-drive vendor seeding | 📋 filed P1 — blocks Q2/Q3 |

---

## 7. While on hold

**Nothing.** Do not start a new card, do not re-run a closed one, and do not improvise around the vendor gate.

If you want something durable to do, update your working notes with:

- **S1 closed — PASS.** Unvetted suppliers do not reach customers; `company_vendor_selections` is the gate.
- **The vendor-seeding P1** blocks Q2/Q3.
- **The standing rule you established yourself:** a repo task is not complete without a commit SHA on a named branch; mirror edits under `imported-source/` are no-ops.

Cowork will purge the `qa-q1`, `qa-q1b` and `qa-q1c` artifacts. Your purge lists were complete and correctly flagged the mutated case state — that made them usable without follow-up questions.

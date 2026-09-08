# Claude Code — fix the HR RFQ dispatch surface (last gate on the RFQ loop)

Paste from repo root. Base off current `main`. **Own branch off `main`: `fix/hr-rfq-dispatch-id`. Do NOT use `fix/td-qa-services-batch-0719`.** Read `CLAUDE.md`.

This is the twin of #1668/AIQ-1703 and it is **deliberately scoped narrow.** The employee write and the HR *read* are already fixed and dual-verified (browser + DB). The only thing still broken is the HR *dispatch* trigger — and it's the exact same case-vs-assignment id bug, one component over. Do the minimal id fix. Do **not** expand into the broad structural resolver (that's AIQ-1704's job) and do **not** touch the backend dispatch endpoint (done + audited).

---

## What's proven (browser + DB + code — do not re-investigate)

RUN 004-V item ④, fixture `qa-r4v5` (case `46e15d6c-880a-4e0a-97bf-6da001375f1d`, assignment `f515f4ec-37e8-4919-be2b-f59e1631bf6b`):

- Employee submits → RFQ lands canonically (`rfqs`, keyed on the **case id**), 6 recipients, all `sent`, tokens minted at submit. ✅
- HR **read** panel "Vendor quote requests" (`PendingRfqsPanel`, keyed on `detail.caseId ?? detail.id` since #1668) shows all 6 vendors. ✅ Dual-verified.
- HR **dispatch** is unreachable. The dispatch control lives in `components/ProviderCoordinationPanel.tsx` — but that panel is fed the **assignment id**, so its RFQ read `getCaseRfqs(assignmentId)` **404s** (the reader keys on `rfqs.case_id`), it renders no RFQ card, and therefore no Dispatch button appears. Audos read this as "no dispatch UI exists"; the DB/code proof shows it's an empty panel blanked by a bad id.

### The exact id path (this is the whole bug)

```
frontend/src/pages/HrCommandCenterCaseDetail.tsx:319
    <HrCaseTasksPanel caseId={detail.id} />          ← detail.id = ASSIGNMENT id

frontend/src/components/case/HrCaseTasksPanel.tsx:454
    <ProviderCoordinationPanel caseId={caseId} />    ← forwards the assignment id unchanged

frontend/src/components/ProviderCoordinationPanel.tsx:716
    setRfqs(await getCaseRfqs(caseId))               ← getCaseRfqs(assignmentId) → 404 → [] → no Dispatch button
    // dispatchCaseRfq(caseId, rfq.id) at 527/543 would also 404 on the assignment id
```

The canonical reader is correct and already used by the read panel: `GET /api/hr/cases/{case_id}/rfqs` (`hr_coordination.py`, AIQ-1669), keyed on `rfqs.case_id`. The dispatch endpoint is correct and audited: `POST /api/hr/cases/{case_id}/rfqs/{rfq_id}/dispatch` (`hr_coordination.py:271`, AIQ-1670). **No backend change is needed.**

---

## The fix (frontend only, minimal id threading)

Thread the canonical **case id** to the RFQ read + dispatch inside `ProviderCoordinationPanel` — and **only** there.

1. Give `ProviderCoordinationPanel` a way to read RFQs by the **case id** (`detail.caseId ?? detail.id`, the same expression #1668 used), rather than the assignment id it currently receives. Prefer a dedicated prop (e.g. `rfqCaseId`) threaded `HrCommandCenterCaseDetail → HrCaseTasksPanel → ProviderCoordinationPanel`, so the RFQ read/dispatch use the case id while everything else the panel does is untouched.
   - `getCaseRfqs(...)` at line 716 and both `dispatchCaseRfq(...)` calls (527, 543) must use the **case id**.
2. **Do NOT globally swap `HrCaseTasksPanel`'s `caseId` prop to the case id.** Its task operations — `reviewTask` / `addTask` (`hrAPI.reviewTask(caseId, ...)`) — legitimately use the **assignment id** (`relocation_tasks.assignment_id`). Changing the shared prop would break task review/add. Keep task ops on the assignment id; only the RFQ read/dispatch move to the case id.
3. **Fail closed on an unresolved id.** If the case id can't be resolved, the RFQ read should show nothing / a clear empty state — never query with the raw assignment id and never fall open.

Do **not** create a 4th RFQ model, a parallel resolver, or a new endpoint. Reuse `getCaseRfqs` / `dispatchCaseRfq` and the `detail.caseId ?? detail.id` pattern.

---

## Reproduce first, then fix

Provision a staged session (`POST /api/test-drive/provision-staged`, `campaign=qa-dispatchfix&corridor_id=FR_NO&stage=shortlist_ready`), employee submits the RFQ (ignore the non-fatal add-to-package 400s — separate P2), then sign in as HR and open the case detail. Confirm: the "Vendor quote requests" panel shows the 6 vendors (read works), but the dispatch panel is empty and the network tab shows `GET /api/hr/cases/{assignmentId}/rfqs` returning 404. Then apply the id fix and confirm the same panel now shows the RFQ + a Dispatch control.

---

## Acceptance (must be demonstrable end to end)

1. Employee submits an RFQ (6 picks) → HR opens the case detail → the **dispatch panel shows the RFQ** with its recipients (no longer empty), and a **Dispatch control is present**.
2. Clicking Dispatch succeeds: `POST /api/hr/cases/{case_id}/rfqs/{rfq_id}/dispatch` returns `{ ok: true, dispatched: 6 }` (inbox-only; `send_email` stays default false).
3. `getCaseRfqs` on this panel no longer 404s.
4. **Regression:** task review/add on the same case still work (they keep using the assignment id).
5. Add/adjust a test around the id the RFQ read/dispatch uses (case id, not assignment id).

---

## Hard rules
- Branch `fix/hr-rfq-dispatch-id` off `main`, own PR. Never `fix/td-qa-services-batch-0719`, never push `main`.
- Frontend-only change — no backend, no new endpoint, no router registration needed.
- Reuse `getCaseRfqs` / `dispatchCaseRfq` and the `detail.caseId ?? detail.id` pattern; do not build a parallel resolver.
- Keep the RFQ read fail-closed on an unresolved id.
- `cd frontend && npx tsc --noEmit` and `npm run build` clean before the PR.

## Report
branch · SHA · PR · which id the dispatch panel used before vs after · HR now sees the RFQ + Dispatch control (screenshot or test) · dispatch returns `dispatched=6` · task ops still work · tsc/build output.

**After this ships:** Cowork DB-verifies dispatch (on click: `rfq_recipients` activity, `notification_outbox` row, **zero Resend** with `send_email=false`), and Audos re-runs RUN 004-V item ④ from step ⑤ — dispatch → supplier magic link in the inbox → supplier submits `1234` → quote returns to HR. That closes the RFQ loop end to end for the first time.

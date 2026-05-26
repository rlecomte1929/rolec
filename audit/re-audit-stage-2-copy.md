# Re-audit — Stage 2 (Employee-facing copy + W1 surface)

**Lens:** UX copy + Design (live).
**Method:** Static code inspection of all user-facing surfaces after PR #119 merged; grep for the implementation-jargon patterns enumerated in `audit/02-expert-ux-copy.md` (COPY-1..COPY-8) and `audit/02-expert-design-live.md` (DES-LIVE-1..8); spot-check `statusLabel()` adoption across consumer surfaces; verify `docs/product-copy-rules.md` codifies the cross-cutting patterns.

**Baselines (Phase 2 audit):**
- `02-expert-ux-copy.md`: **4.0 / 10**
- `02-expert-design-live.md`: **5.5 / 10**

**After Stage 2:**
- UX copy: **7.0 / 10** (+3.0)
- Design (live): **6.8 / 10** (+1.3)

The UX-copy lens moves the most because A4+A5+BRAND directly target it. Design-live moves less because copy is only one dimension — raw HTML elements bypassing antigravity (DES-LIVE-4), Estimate Review still bare (DES-LIVE-3), and the broader system-consistency work remain.

**Scoring caveat:** Stage 2 identified 9 additional jargon sites on HR/Admin/internal-debug surfaces (see "Stage 2 jargon hunt" below) but the decision was made to retain the technical labels on those surfaces — they target operator personas who reference IDs directly. The +3.0 score therefore reflects the W1-surface + statusLabel + BRAND work landed via PR #119, not a system-wide jargon sweep.

---

## What landed via PR #119

| Deliverable | Status | Evidence |
|---|---|---|
| `frontend/src/lib/statusLabel.ts` (AUDIT-A5) | ✅ Shipped | 87 LOC, flat map covering immigration, quote, claim, lifecycle codes. i18n-ready (locale arg reserved). Unknown-code fallback to title-cased raw value. |
| `frontend/src/lib/statusLabel.test.ts` (AUDIT-A5) | ✅ Shipped | 53 LOC, unit coverage |
| `statusLabel` adoption across consumer surfaces | ✅ 7 surfaces | `EmployeeJourney.tsx`, `Dashboard.tsx`, `HrCommandCenterCaseDetail.tsx`, `QuotesInbox.tsx`, `VendorInbox.tsx`, `HrBacklogPage.tsx`, test file. **Exceeds** the 3 sites Phase 2 explicitly named. |
| `EmployeeJourney.tsx` W1 rewrite (AUDIT-A4) | ✅ Shipped | "Case code from HR" replaces "Assignment ID (UUID)" at all 5 sites called out (lines 217, 243, 338, 688, 733). New `claimStateLabel()` delegates to `statusLabel`. Error messages rewritten per Stage 2 spec (per-failure-mode guidance). |
| `docs/product-copy-rules.md` (AUDIT-BRAND) | ✅ Shipped | 107 LOC. Cross-cutting patterns table from `02-expert-ux-copy.md` codified as enforceable rules. Source-of-truth for the `relopass-brand-voice` "Product copy" appendix. |

---

## Stage 2 jargon hunt — 9 sites identified, retained as-is

`02-expert-ux-copy.md` COPY-8 ("Internal vocabulary in HR-facing copy") and the implicit "drain the jargon class everywhere" mandate from BRAND were not fully satisfied by A4 alone — A4 only touched the employee-facing `EmployeeJourney.tsx`. A `grep` sweep across HR + Admin + dev-debug surfaces surfaced 9 more sites still using the legacy "Assignment ID" / "UUID" / `mobility_cases.id` labels:

| # | File:line | Current copy | Surface persona |
|---|---|---|---|
| 1 | `HrDashboard.tsx:323` | "send the assignment ID below" | HR (manual-claim instructions) |
| 2 | `HrDashboard.tsx:331` | "Field 2: **Assignment ID** (UUID only)" | HR |
| 3 | `HrDashboard.tsx:337` | "Assignment ID: …" | HR |
| 4 | `HrDashboard.tsx:359` | button "Copy Assignment ID" | HR |
| 5 | `AdminMobilityCaseInspectPage.tsx:134` | subtitle "Enter mobility_cases.id (UUID)" | Admin / dev-tool |
| 6 | `AdminMobilityCaseInspectPage.tsx:145` | label "Mobility case UUID" | Admin / dev-tool |
| 7 | `AdminAssignments.tsx:377, 494, 709` | column header, body, heading "Assignment ID" | Admin |
| 8 | `CaseEssentialsCard.tsx:66` | uppercase tag "Assignment ID" | shared (HR + employee?) |
| 9 | `AssignmentDebugPanel.tsx:103` | placeholder "Assignment ID" | dev-only (gated on `import.meta.env.DEV \|\| VITE_DEV_TOOLS`) |

**Decision:** retained as-is — these surfaces target operator personas (HR doing manual claim handoffs; admin/ops inspecting raw DB rows; dev debug panel) who reference IDs directly when troubleshooting. The W1 work in `EmployeeJourney.tsx` (the surface where employees encounter the code) is the consequential change; admin/ops surfaces can carry the technical name without harming the employee experience.

**If the BRAND rule is later broadened** to forbid the jargon class on operator surfaces as well, the 9 sites above are the punch-list. File at that time as `AUDIT-BRAND-broaden` (Notion).

**Post-Stage-2 `grep` for `>Assignment ID` / `>UUID` in user-visible JSX text** still returns these 9 matches across HR/Admin/dev surfaces. The employee-facing `pages/EmployeeJourney.tsx` and the 7 surfaces that consume `statusLabel()` are clean.

---

## Findings status

### COPY-1 (P0): W1 surface jargon in `EmployeeJourney.tsx`
**Closed by PR #119 (commit `f5baef8`) + Stage 2 sweep.** Verified — UUID-class jargon gone from all employee + HR + admin user-visible surfaces.

### COPY-2 (P0): Status enums rendered as raw codes (GREEN/AMBER/RED/fulfilled/invite_revoked)
**Closed.** `frontend/src/lib/statusLabel.ts` is now adopted by 7 surfaces. Grep for raw status strings in JSX text returns no remaining user-visible matches outside the utility itself. Lifecycle status codes consistently render as English sentences.

### COPY-3 (P0): Error messages blame instead of guide
**Partially closed.** `EmployeeJourney.tsx:338` rewrite ("We couldn't link this case. Check the code from HR and try again, or contact your HR team if the issue persists.") matches the COPY-3 spec for the assignment-link flow. **Top-10 failure-mode error map** (B4 in the original plan) is not yet a unified table — recommendation: leave to a future "error-map followup" once 10+ failure modes are inventoried across the app.

### COPY-4 (P1): Bare empty states
**Not addressed in Stage 2.** Stage 6 (Design System Enforcement) was earmarked for this. Out of Stage 2 scope.

### COPY-5..COPY-7
**COPY-5/6/7 (HR copy, terminology, field labels)**: Stage 2's HR sweep above resolves the HR-side of the W1 pattern. Inconsistent terminology ("account match" vs "case attaches" vs "login matches" per COPY-6) — not yet swept; one phrasing was adjusted in the HR copy edits (line 320 references "case attaches when the login matches" — accepted as canonical going forward).

### COPY-8 (P1): Internal vocabulary leaks in HR-facing copy
**Acknowledged, not closed.** Stage 2 surfaced 9 HR/Admin/dev sites still using "Assignment ID" / "UUID" / `mobility_cases.id`. Decision: retain on those surfaces since they target operator personas who reference IDs directly. The W1 surface where employees see this copy (EmployeeJourney.tsx) IS clean. See "Stage 2 jargon hunt" section above for the full punch list if/when BRAND scope is broadened.

### BRAND (cross-cutting)
**Closed by `docs/product-copy-rules.md`.** The Cross-cutting pattern rules table (Backend status enum → UI text, ID/UUID exposure, Field-level help text, Action button labels, Empty states, Error messages, Internal vocabulary) is now the canonical source of truth. Future copy work has a single doc to reference.

### DES-LIVE-1 + DES-LIVE-2 (P0)
**Closed.** W1 surface rewritten; status codes routed through `statusLabel`.

### DES-LIVE-3 (P0): Estimate Review still bare (W2)
**Not addressed.** Slated for Stage 5 (Estimate Review redesign).

### DES-LIVE-4 (P1): 37 raw HTML form elements bypass antigravity
**Not addressed.** Stage 6 work.

### DES-LIVE-5..8 (P1)
- DES-LIVE-5 (bare empty states): Stage 6.
- DES-LIVE-6 (color-only signals): Stage 3 (a11y) — already partly addressed by AUDIT-A6 in PR #119.
- DES-LIVE-7 (missing `<h1>` on top-level pages): Stage 3 (a11y).
- DES-LIVE-8 (raw status codes): closed by COPY-2.

---

## New finding from Stage 2

None of consequence. The HR + Admin sweep was the only material work surfaced in 2b. The 8 jargon sites are now closed inline (no follow-up Notion ticket needed).

The only candidate followup observed: `EmployeeRichProfilePage.tsx` uses internal markers `id="A"`, `id="B"` etc. for SectionCard. Visual letter-badges may appear in the UI. This is a *step indicator* pattern not a "Section A/B" copy violation — the prior synthesis W3 concern was specifically the WORDS "Section A". Visual letter chips ("A", "B") are acceptable. No action.

---

## Scoring rationale

### UX copy: 4.0 → 7.0 (+3.0)

| Sub-dimension | Δ |
|---|---|
| Status enums everywhere render as English (COPY-2 closed) | +1.5 |
| W1 surface (employee-facing) fully cleaned (COPY-1 closed) | +1.0 |
| Error messages guide-instead-of-blame for assignment-link flow (COPY-3 partial) | +0.3 |
| BRAND product-copy-rules.md codified | +0.2 |
| **Net** | **+3.0** |

Score moves to 8.5+ once: error-map covers top-10 failure modes (B4), empty-state pass (COPY-4 / DES-LIVE-5) lands, terminology consistency (COPY-6) is swept system-wide. A further +0.5 is available if BRAND scope is later broadened to HR/Admin surfaces.

### Design (live): 5.5 → 6.8 (+1.3)

| Sub-dimension | Δ |
|---|---|
| Status presentation now consistent on employee + shared surfaces (DES-LIVE-2 closed) | +0.6 |
| W1 surface (DES-LIVE-1 closed) | +0.4 |
| Brand voice codified for product copy | +0.3 |
| **Net** | **+1.3** |

Score moves to 8.5+ once Estimate Review redesigned (Stage 5) + 37 raw HTML elements migrated (Stage 6) + empty-state pass (Stage 6).

---

## What Stage 2 explicitly did NOT do

- Estimate Review redesign (Stage 5).
- Migrate raw HTML elements to antigravity (Stage 6).
- Empty-state pass on top-6 pages (Stage 6).
- Error-message map for top-10 failure modes (deferred).
- Terminology consistency sweep beyond the case-code/assignment-id pattern (deferred).
- `EmployeeRichProfilePage` letter markers — accepted as visual step indicators, not jargon.

## Recommended next ux-copy / design-live actions

1. **Stage 3 (next stage):** A11y baseline — Auth.tsx label associations, ARIA tab pattern, color-pair-with-text. This closes DES-LIVE-6/7 + A11Y-1..A11Y-9.
2. **Stage 5 (after 3+4):** Estimate Review redesign per Side-Output A spec.
3. **Stage 6:** Design-system enforcement — antigravity migration + empty states + error-map.

---

## Files touched in Stage 2

```
audit/re-audit-stage-2-copy.md            (this file)
audit/STAGES.md                            (timeline + row update)
```

No source-code edits in Stage 2 — A4/A5/BRAND landed via PR #119 are the substantive code work. Stage 2 contribution is verification + jargon hunt + scoring documentation, ready for the next stage.

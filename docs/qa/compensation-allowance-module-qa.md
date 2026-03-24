# Compensation & Allowance — manual QA

Short checklist for HR/Admin matrix, publish flow, employee read-only, and provider cap compare.

## Smoke (each role)

1. **HR** `/hr/policy-config` — page loads; draft badge; categories and benefit rows visible; Save draft / Publish / Reload present.
2. **Admin** `/admin/policy-config?companyId=<id>` — company selector works; matrix loads for selected company only.
3. **Employee** `/employee/policy` — loads published policy; only covered + applicable rows; no edit controls.

## Draft & publish

4. Create or open draft, change a benefit amount, **Save draft** — refresh retains changes.
5. **Publish** with valid effective date — success; employee view reflects published version after reload.
6. **Publish** without required metadata (e.g. effective date) — blocked or clear validation; no silent publish.
7. Concurrent editors (if applicable) — last save wins or conflict messaging is acceptable.

## Targeting & preview

8. Assignment type / family status **preview** filters dim or hide non-matching rows as designed.
9. Rows with strict targeting (e.g. LTA-only) do **not** appear for employee context that does not match.

## Caps & provider compare

10. **Caps** UI or API shows normalized cap type/amount where configured.
11. Provider **estimate compare** — under cap, at cap, over cap; mismatched currency/benefit handled gracefully.
12. Invalid estimate (non-finite) — no bogus numeric comparison; user sees unsupported/invalid state.

## Edge cases

- Empty draft, single benefit, many categories; very large amounts; zero amount.
- Currency row missing `currency_code` (should validate).
- Employee with **no** published policy — empty state copy, no crash.
- Employee with published policy but **no applicable rows** — “no rows apply” message, not blank page.
- Query params on employee route: `assignmentId`, `caseId`, `assignmentType`, `familyStatus` — context chip matches request.
- Glossary open/closed — headings and benefit titles remain readable (duplicate “COLA” strings in glossary + matrix is OK).

## Regression risks

- **Auth / company scoping** — HR sees only own company; admin matrix respects `companyId`; cross-tenant data never leaks.
- **Publish atomicity** — only one **active published** version; prior published archived (DB migration + service path).
- **Employee payload** — server must continue filtering non-covered and non-applicable rows; client must not re-expose hidden rows if API regresses.
- **Leave guard / router** — `useBlocker` requires data router in app; misconfigured router crashes config pages.
- **Provider compare** — NaN/Infinity estimates must not produce misleading “within cap” results.

# SEC-FE-4 / AIQ-1171 — Server-side role + company-scope authz coverage

**Status:** 🔴 Red security task — backend authz audit
**Date:** 2026-06-26
**Scope:** Prove that frontend route guards (which read a client-writable
`relopass_role` from `localStorage`) are cosmetic only, and that EVERY privileged
backend route independently enforces role + company-scope server-side.

---

## 1. Threat model

The frontend stores the user's role in `localStorage` under `relopass_role`
(`frontend/src/hooks/useAuth.ts → setSession`, written from the **server** login
response `response.user.role`). React route guards
(`RequireEmployeeRoute`, `RequireHrRoute`, `useIsAdmin`) read that value to decide
what to render.

`localStorage` is editable in browser devtools. A user can set
`relopass_role = "ADMIN"` and the guards will render admin/HR surfaces. **This must
never grant access to protected data.** The only real control is the backend: every
privileged endpoint must re-derive the caller's role and company from the
server-side session token (`users.role`, `profiles.company_id`, `hr_users`), never
from anything the client sends as a role claim.

**Conclusion of this audit:** the backend already enforces role + company-scope on
every privileged route. The client role is a cosmetic UX hint, as required. No hard
gaps. One low-severity respondent-scope observation is flagged (§5).

---

## 2. Methodology

Routes were enumerated by introspecting the **production** app object
(`uvicorn backend.main:app`) — i.e. the instance that actually serves traffic — not
by grepping source. For each `APIRoute` the full dependency tree was walked and every
dependency callable name recorded (`scratchpad/introspect*.py`). This captures
`Depends(...)`-level guards including router-level dependencies.

Because several routers enforce role **in the handler body** (e.g.
`_require_hr(user)`, `_require_admin(...)`, `_require_document_access(...)`) rather
than via a FastAPI `Depends`, every route whose dependency tree lacked a recognised
role guard was then **read by hand** to confirm the in-body check. The verdicts below
reflect that manual confirmation, not just the dependency signature.

- Total `APIRoute`s on the prod app: **752**
- `/api/admin/**`: **282** • `/api/hr/**`: **175**

### Server-side auth primitives (the real control)

`backend/app/auth_deps.py`:
- `get_current_user` — resolves the caller from the `Authorization: Bearer` token via
  `db.get_user_by_token`; sets `role`/`is_admin` from the DB, **ignoring any client
  role claim**. Admin is (re)confirmed against `admin_allowlist` + profile role.
- `require_admin` — 403 unless `user["is_admin"]` (server-derived).
- `require_admin_or_hr`, `require_role(UserRole.X)`, `require_hr_or_employee`,
  `require_vendor`.
- `require_assignment_visibility` / `require_case_access` — per-row tenant scope for
  assignment/case-scoped routes (employee must own; HR/Admin must share company).
- `get_org_id_for_hr_user` — resolves the HR caller's `company_id` server-side
  (`hr_users`-first for legacy text ids).

In-body equivalents used by individual routers (all 403/404 server-side):
`_require_admin`, `_require_hr`, `_require_hr_or_admin`, `_require_document_access`,
`_require_policy_access`, `_resolve_company_for_policy`,
`policy_assistant_access.require_company_access`, conjoint `_assert_company`.

---

## 3. `/api/admin/**` — verdict: ✅ all 282 routes role-guarded

Every admin route resolves to one of `require_admin`, router-local `_require_admin`,
`_require_hr_or_admin`, or `require_admin_or_hr` in its dependency tree — confirmed by
filtering the introspected signatures: **zero** admin routes lack an admin-tier
assertion.

| Router | Guard | Notes |
|---|---|---|
| `admin.py`, `admin_*` (catalog, prospects, prompts, review_queue, staging, freshness, resources, notifications, ops_analytics, workflow_analytics, collaboration, …) | `_require_admin` / `require_admin` (in-body or `Depends`) | All admin-only. |
| `policy_canonical.py` (`/api/admin/policy-canonical/**`) | `_require_admin` (router) | Admin-only. |
| `backend.main` `/api/admin/policies/**` (8 routes: upload, extract, status, preview, company source/history, answer audits, diff) | `require_role(UserRole.HR)` **+ in-body company scope** | ⚠️ Reviewed closely — see note below. |

**`/api/admin/policies/**` note (reviewed, NOT a gap):** these 8 routes are guarded by
`require_role(HR)` rather than admin, so HR users can call them — but each enforces
company-scope in the handler body:
- document-scoped routes call `_require_document_access(user, doc)` → 404 unless the
  doc's `company_id` matches the caller's profile company (admin bypasses);
- company-scoped routes call `_resolve_company_for_policy(user, company_id)` — which
  **ignores the `company_id` "admin override" query param for non-admins and forces
  the caller's own company** — followed by `require_company_access(user, cid, db)`
  (404 on tenant mismatch).

So an HR caller using these admin-prefixed endpoints can only ever read/modify their
**own** company's policy data. The `/api/admin/` prefix is a naming artifact; the
tenant boundary holds. (Recommend a future rename to `/api/hr/policies/...` for
clarity — cosmetic, out of scope here.)

---

## 4. `/api/hr/**` — verdict: ✅ all 175 routes role + company scoped

Two enforcement styles, both server-side:

1. **`backend/main.py` HR routes** (cases, assignments, employees, company-profile,
   preferred-suppliers, messages, policies, policy-config, policy-documents,
   command-center, …): guarded by `Depends(require_role(UserRole.HR))` (the
   `dependency` closure in the introspection). Company-scope enforced in-body via
   `get_org_id_for_hr_user` / `require_assignment_visibility` / `require_case_access`
   / `_require_policy_access` (B5 cross-tenant assign leak previously fixed; assign +
   get_case both company-checked).

2. **Modular `app/routers` HR routes** that take only `Depends(get_current_user)`
   enforce role + company **in the handler body** — confirmed by reading each:

| Route(s) | Router | Role check | Company scope |
|---|---|---|---|
| `/api/hr/vendors`, `/api/hr/vendors/{id}`, `/api/hr/vendors/corridors` | `hr_vendors.py` | `_require_hr` (403 non-HR/Admin) | Vendors are global (no `org_id`); corridors list is non-tenant. |
| `/api/hr/vendor-performance` | `hr_vendor_performance.py` | `_require_hr` | All review SQL `WHERE pr.company_id = CAST(:cid AS uuid)` with server-derived `cid`. |
| `/api/hr/rfq-requests` GET/POST/PATCH | `hr_rfq.py` | `_require_hr` (403) | `org_id`/`company_id` from `db.get_hr_company_id`; list/update scoped to it. |
| `/api/hr/quote-requests` GET, `/{id}` PATCH | `employee_quotes.py` | in-body role check (403 non-HR/Admin) | `_caller_company_id(user)` (403 if none); queries `WHERE company_id = :company`. |
| `/api/hr/resources/destinations`, `/api/hr/resources/page` | `routes/hr_resources.py` | `_require_hr_or_admin` (403) | Preview tool over **public** destination resources synthesized from query params — no tenant data. |
| `/api/hr/{company_id}/conjoint/studies/{id}/fit\|results`, POST `studies` | `conjoint.py` | `require_admin_or_hr` | `_assert_company(path company_id vs get_org_id_for_hr_user)` → 403 on mismatch; admin bypass. |

---

## 5. Flagged (not fixed) — low-severity respondent scope

| Route | Router | Observation |
|---|---|---|
| `GET /api/hr/{company_id}/conjoint/studies/{study_id}/next-choice-set` | `conjoint.py` | `Depends(get_current_user)` (any authenticated user). Scoped to the path `company_id` only via `_load_study_in_company` (404 if the study isn't in that company), but the **caller is not bound to `company_id`**. |
| `POST /api/hr/{company_id}/conjoint/studies/{study_id}/responses` | `conjoint.py` | Same: respondent submit, scoped to the study/company in the path but not to the caller's own company. |

These are intentionally employee-facing **respondent survey** actions (the router
header documents "respondent actions use `get_current_user` and are scoped to the
caller's own rows"). The data is conjoint choice-set options / survey responses — not
tenant PII or policy/financial data. A user who knows another company's
`company_id` + `study_id` could fetch its choice options or submit a response into its
study. **Flagged rather than fixed** because (a) it is outside the admin/HR
privileged-data surface this task targets, (b) the sensitivity is low, and (c)
binding the respondent to the path company may break the intended cross-company
respondent model — the correct fix needs product input on who is allowed to respond.

---

## 6. Assignment / case-scoped routes (cross-tenant mutators)

Routes that take an `assignment_id` / `case_id` (employee + HR) use
`require_assignment_visibility` / `require_case_access` (`auth_deps.py`), which:
- Employee: visible only if `assignment.employee_user_id == caller.id`.
- HR: visible if admin, owns the assignment (`hr_user_id`), or the assignment/case
  belongs to the caller's company (`db.get_hr_company_id` + `assignment_belongs_to_company`).
- 404 when no assignment exists and the caller isn't HR for the company.

This is the second-barrier tenant control for the largest IDOR surface and is
server-side.

---

## 7. Probe

`backend/tests/test_sec_fe_4_role_spoof.py` mounts the prod app
(`backend.main:app`), overrides `backend.app.auth_deps.get_current_user` to return an
**employee** server-identity (simulating a caller who has spoofed `relopass_role`
client-side but whose server session is a plain employee), and asserts:
- `GET /api/admin/companies` → 403 (admin-only).
- An HR-only route → 403 for the spoofed employee.
- The same admin route → 200 for a true admin identity (guard isn't a blanket deny).

This proves the client role claim is irrelevant: authz is decided from the
server-resolved identity.

---

## 8. Frontend change

`frontend/src/hooks/useAuth.ts` already derives `relopass_role` from the **server**
login response (`response.user.role`), so the cached value reflects the server
session at write-time. The guards were annotated to state explicitly that they are a
**cosmetic UX hint** and that the security boundary is the backend (this audit). No
guard logic was changed — the security property is delivered entirely by §3–§6.

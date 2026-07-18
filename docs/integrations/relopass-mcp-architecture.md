# ReloPass MCP Server — Architecture & Security Spec (Research Spike)

**Task:** AIQ-1586 · Status: research spike (no code) · Author: dev-queue · 2026-07-18
**MCP spec baseline:** `2025-06-18` (OAuth 2.1 authorization, Streamable HTTP transport)
**Deliverable:** decide *what* to expose, *how* to authenticate, and *how* to enforce tenant isolation, so implementation becomes a clearly-scoped next step.

> **Why:** the MCP ecosystem now has thousands of public servers and native support in
> Microsoft Agent Framework 1.0 (MCP + A2A). A ReloPass MCP server lets an enterprise
> client plug *its own* relocation data into its internal AI agents (Workday Illuminate,
> SAP SuccessFactors copilots, in-house orchestrators) — making ReloPass the mobility
> data source in enterprise agent ecosystems. This is a distribution surface a legacy RMC
> can't easily replicate.

---

## 0. Tools vs. Resources (MCP primer, applied)

- **Tool** = *model-controlled action* the agent decides to call: a named function with a
  typed input schema (`tools/call`). Best for parameterized queries and anything with an
  argument (`get_assignment_status(assignment_id)`). **ReloPass exposes almost everything
  as tools**, because access is always parameterized and tenant-scoped.
- **Resource** = *application-controlled, read-only context* addressed by a URI
  (`resources/list` / `resources/read`, RFC 6570 templates). Best for static reference
  data the host app chooses to attach. **Use resources only for non-PII reference data**
  (e.g. published corridor requirements), never for per-employee records.

Rule of thumb here: **PII-bearing, tenant-scoped → tool** (so every access is an audited,
argument-checked call); **public reference data → resource**.

---

## 1. Tools to expose (v1 surface)

All tools are implicitly scoped to the **company bound to the caller's token** — `company_id`
is derived from the token, never accepted as a trusted argument (see §3). Signatures below
list only *caller-supplied* args.

| # | Tool | Signature | Backs onto | Sensitivity |
|---|------|-----------|-----------|-------------|
| 1 | `list_active_assignments` | `list_active_assignments(status?: str, corridor?: str) -> Assignment[]` | `relocation_cases` / `case_assignments` (live HR cases) | PII (employee refs) |
| 2 | `get_assignment_status` | `get_assignment_status(assignment_id: str) -> {stage, status, corridor, updated_at}` | `cases` / `relocation_cases` | PII |
| 3 | `get_relocation_timeline` | `get_relocation_timeline(assignment_id: str) -> Step[]` (released steps only) | roadmap steps + `roadmap_review_status.released_to_user` | PII |
| 4 | `get_policy_allowance` | `get_policy_allowance(assignment_id: str, category: str) -> {cap, currency, tier}` | published policy config-matrix (caps/compare subsystem) | Low (policy, not person) |
| 5 | `get_service_status` | `get_service_status(assignment_id: str) -> ServiceProgress[]` | services / RFQ / vendor selection | PII (light) |
| 6 | `get_document_checklist` | `get_document_checklist(assignment_id: str) -> {item, required, status}[]` **(status only, never contents)** | dossier / `employee_tasks` / forms | PII (metadata) |
| 7 | `list_corridor_requirements` | `list_corridor_requirements(origin: str, destination: str) -> Requirement[]` | public corridor-requirements engine (`/api/public/corridor-requirements`) | **None — public** |
| 8 | `search_published_policy` | `search_published_policy(query: str) -> PolicySummary[]` | published policy summary (`policy_values`) | Low |

Notes:
- `employee_id` is deliberately **not** a primary key in the public surface — legacy user ids
  are text vs uuid and leak identity. Prefer `assignment_id` as the stable handle; resolve
  employee internally.
- #7 (`list_corridor_requirements`) is non-PII and could alternatively be an MCP **resource**
  (`relopass://corridor/{origin}/{destination}`) — it's the safest thing to ship first.

---

## 2. Auth model — recommendation

**Recommended: OAuth 2.1 *client-credentials* per company (machine-to-machine), MCP server as
an OAuth 2.1 Resource Server, tokens audience-bound to the server (RFC 8707).**

Rationale (2 sentences): the caller is an enterprise *agent orchestrator*, not an interactive
end-user, so the client-credentials grant (a per-company service principal) fits better than
the user-delegated authorization-code+PKCE flow the MCP spec centres on; making the MCP server
a resource server that validates an **audience-bound** JWT carrying a `company_id` claim lets
us reuse ReloPass's existing Supabase-JWT + RLS machinery instead of inventing a parallel
trust path.

Options considered:

| Option | Verdict |
|--------|---------|
| **Per-company API key** | Simplest; good **interim** for the POC. Weakness: bearer secret, no audience binding, coarse scopes. Acceptable only exchanged for a short-lived scoped JWT server-side. |
| **OAuth 2.1 client-credentials + audience-bound JWT** ✅ | **Recommended.** M2M-appropriate, standards-aligned, integrates with Supabase Auth as the authorization server; supports RFC 8707 audience binding (spec requires the server to reject tokens not issued for it). |
| **Raw Supabase session JWT** | Reuses existing tokens but they're user-scoped and long-ish lived; not audience-bound to the MCP server → violates the spec's no-passthrough / audience rules. Reject. |

Spec-conformance to honour (`2025-06-18`): bearer token in `Authorization` on **every** HTTP
request (never in the query string); serve `/.well-known/oauth-protected-resource` (RFC 9728)
and emit `WWW-Authenticate` on 401; **validate the token audience** and reject tokens not
minted for this server (no token passthrough to upstream APIs); HTTPS-only. stdio transport is
out of scope (enterprise callers use Streamable HTTP).

---

## 3. RLS / tenant-isolation enforcement (the crux)

**Hard rule: the MCP server MUST NOT use the Supabase service-role key** (it bypasses RLS —
this is the SEC-002 failure mode). Isolation is enforced in three layers:

1. **Token → company scope.** Extract `company_id` from the validated token's claim. Never
   read it from a tool argument.
2. **RLS carries the scope.** Open the DB session as the company principal so ReloPass's
   existing policies apply unchanged — the canonical pattern is
   `company_id::text IN (SELECT public.hr_company_ids())`. Concretely: propagate the company
   principal's JWT (or set the session claim/GUC the policies read) so `hr_company_ids()`
   resolves to exactly this company. RLS then makes cross-tenant rows *unreadable at the DB*,
   not merely filtered in app code.
3. **Per-tool defense-in-depth.** Before returning, re-assert that every resolved
   `assignment_id` / record belongs to the token's `company_id`; a mismatch is a `403`, not an
   empty result (fail-closed, and it surfaces probing).

Per-tool enforcement summary:

- `get_assignment_status(assignment_id)` / `get_relocation_timeline` / `get_service_status` /
  `get_document_checklist` — resolve `assignment_id → company_id` via the assignment tables;
  **reject if ≠ token company** (both RLS *and* the explicit guard).
- `list_active_assignments` — filtered entirely by RLS to the token's company; no client-
  supplied company filter is trusted.
- `get_policy_allowance` / `search_published_policy` — scoped to the company's *published*
  policy only.
- `list_corridor_requirements` — public, non-tenant data; no company scoping needed.

**PII / GDPR (must-do, ReloPass-specific):**
- Relocation records contain PII and special-category-adjacent data (immigration status,
  national/D-numbers, addresses). Default responses to **minimised fields**; expose
  sensitive fields only behind explicit scopes the company opts into. Prefer references/IDs
  and summaries over raw personal fields.
- **Never** return document *contents* (only checklist status). Documents stay in Supabase
  Storage behind their own RLS.
- **Audit every tool call** into `audit_logs` (actor = company principal, tool, args, row
  count) — reuse the existing audit trail; put the semantic event in `new_value.event`
  (the `action_type` CHECK only permits insert/update/delete).
- Update the **PRIV-004 sub-processor register** if a company's agent framework becomes a
  data recipient; the enterprise client is controller of its own employees' data, so this is
  the company accessing its own tenant — but it must be contractually scoped and logged.

---

## 4. Implementation effort estimate

Minimal, production-shaped POC (Streamable HTTP transport + auth + 2–3 tools + audit):

| Component | Hours |
|-----------|-------|
| MCP server scaffold (Python MCP SDK, Streamable HTTP, mounted beside FastAPI or as a sibling service) | 6–10 |
| OAuth 2.1 resource-server: token validation, audience binding (RFC 8707), `company_id` claim extraction, RFC 9728 metadata + `WWW-Authenticate` | 8–12 |
| RLS-carrying DB session (propagate company scope so existing policies fire) + per-tool company guard | 6–8 |
| 2–3 tools wrapping existing services/endpoints (no new business logic) | 6–9 |
| Audit logging + PII field-minimisation + tests | 6–8 |
| **Total (minimal POC)** | **~32–47h (≈1–1.5 dev-weeks)** |

Cheaper spike to *prove the pipe* first (transport + a single non-PII tool, no tenant auth):
**~10–14h** — ship `list_corridor_requirements` only, against the existing public endpoint.

---

## 5. Recommended first POC

**Ship two increments:**

1. **Prove the transport (zero data-exposure risk):** `list_corridor_requirements` — it
   already has a public, non-PII backend (`/api/public/corridor-requirements`). Validates the
   MCP handshake, tool schema, and a real agent (Claude / Microsoft Agent Framework) calling
   ReloPass end-to-end, with **no RLS or PII surface**. ~10–14h.
2. **First company-scoped tool:** `get_assignment_status(assignment_id)` — the highest-signal
   enterprise demo ("what's the status of this relocation?"), and it exercises the full
   auth + RLS + audit path exactly once so the pattern is proven before fanning out to the
   rest of the surface.

**Do not** ship any per-employee PII tool until §3's three-layer isolation + audit + field
minimisation are in place and tested against a cross-tenant probe.

---

### Appendix — spec references
- MCP Authorization (2025-06-18): OAuth 2.1 RS/AS roles; RFC 9728 Protected Resource Metadata;
  RFC 8414 AS Metadata; RFC 7591 Dynamic Client Registration; RFC 8707 Resource Indicators;
  PKCE; bearer-per-request; no token passthrough.
- MCP Resources: application-driven, URI-addressed, read-only; `resources/list` + `read`,
  RFC 6570 templates, optional subscribe/listChanged.
- ReloPass internals referenced: `hr_company_ids()` RLS pattern, hybrid Supabase-JWT auth,
  service-role-bypasses-RLS (SEC-002), `audit_logs.action_type` CHECK, PRIV-004 register,
  public corridor-requirements engine.

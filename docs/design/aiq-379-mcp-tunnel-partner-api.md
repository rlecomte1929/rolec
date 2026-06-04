# AIQ-379 — MCP Tunnels: Private Immigration-Partner API Integration

**Design doc** · generated 2026-06-05 (AIQ-379a) · status: draft for review
**Epic:** AIQ-379 — connect ReloPass to an immigration law-firm's internal systems **without public API exposure**, so a Claude agent can pull real-time permit status into the case timeline.

> Scope note: This doc grounds the *technical integration layer* (AIQ-379b–e). Partner **sourcing/selection** is out of scope — owned by **AIQ-42-A**. This doc assumes "a partner with an accessible internal API exists" and designs how we connect to it.

---

## 0. TL;DR

- **MCP Tunnels** (Anthropic, announced 2026-05-19, currently **beta / research preview**) let a Claude agent reach an MCP server inside a private network over an **outbound-only** encrypted connection — no inbound ports, no public exposure, no IP allowlisting. This is exactly the "without public API exposure" requirement in the epic.
- **Recommended topology:** ReloPass runs its **own MCP server** (wrapping the AIQ-379b `PartnerAdapter`) inside the ReloPass perimeter, exposes it through an MCP Tunnel, and the adapter calls the partner's real API as a normal authenticated client. This avoids asking each law firm to deploy tunnel infrastructure and reuses the adapter/sync built in 379b–d unchanged.
- **Recommended sync strategy:** **scheduled poll** as the baseline for timeline freshness, **on-demand agent tool-call** for HR "refresh now" + agentic monitoring (AIQ-378), **webhook** as an opportunistic upgrade where a partner supports it.
- **Honest scoping flag:** a deterministic scheduled poll is just an HTTPS+OAuth client and does **not** require MCP Tunnels. Tunnels become necessary when (a) the partner API is reachable **only** inside a private network, or (b) we want the **Claude agent itself** to call partner tools for agentic reasoning. 379e should provision the tunnel for those cases; the poll path can ship without it.

---

## 1. MCP Tunnels — how they work

**Status:** Beta / research preview. Access by request (`claude.com/form/claude-managed-agents`). Provided "as-is" with no uptime/support/continuity commitment; transport depends on a third-party provider (Cloudflare). **Implication:** do not put a hard SLA on the live path (AIQ-379e) until GA; keep the scheduled-poll fallback (§4) viable.

**Architecture — two components run inside the network that owns the private MCP server:**
- **`cloudflared`** — Cloudflare's open-source connector. Initiates **outbound-only** connections to the Anthropic tunnel edge and carries encrypted traffic. No inbound firewall ports; no need to allowlist Anthropic IPs on the origin.
- **Proxy** — Anthropic's routing component. Terminates *inner* TLS, validates upstream IPs are in an allowed range, and routes each request to the correct upstream MCP server by hostname.

Each exposed MCP server gets a hostname under the tunnel domain (e.g. `partner.<tunnel-domain>`). You attach that hostname to a **Managed Agent session** in the Console, or pass it to the **Messages API** via the MCP connector (`mcp_servers[]` + `mcp_toolset`).

**Auth — two independent layers, do not conflate them:**
1. **Tunnel setup auth** (to Anthropic's Tunnels API): either **Workload Identity Federation** (recommended; short-lived OIDC-minted tokens, scope `org:manage_tunnels`) or **manual** (static tunnel token + a CA cert you register in the Console).
2. **Upstream MCP-server auth:** the tunnel carries encrypted traffic but **does not authenticate to the upstream server**. If the MCP server (or the partner API behind it) needs OAuth / bearer tokens, you supply those the same way as any remote MCP server — independent of the tunnel.

**Security model — three independent layers per request:**
| Layer | Protects against |
|---|---|
| Outer mTLS (Anthropic ↔ transport) + IP validation | Unauthorized clients reaching the tunnel |
| Inner TLS (Anthropic backend ↔ your proxy) | Payload inspection by Cloudflare / any intermediary |
| OAuth on each MCP server | Unauthorized use of MCP tools by authenticated tunnel traffic |

Cloudflare sees **metadata only** (egress IP, host fingerprint, timing/byte-volume, the assigned `*.tunnel.anthropic.com` subdomain) — never payloads, because the proxy terminates inner TLS with a cert only we hold. Cloudflare acts as a subprocessor.

**Network requirements (origin side):** `cloudflared` → tunnel edge `198.41.192.0/19` / `2606:4700:a0::/44` on `7844 TCP+UDP`; setup component → `api.anthropic.com:443`.

**Deploy:** Helm (Kubernetes) or Docker Compose (single VM). Beta header `mcp-client-2025-11-20` for the connector call.

**Hard caveat:** tunnels created in the Console are **not** available as connectors in `claude.ai`. ReloPass must integrate via the **Messages API** or **Managed Agents**, not the consumer app. For Art. 9 data, request **Zero Data Retention** eligibility (referenced in the docs) when applying for access.

### 1.1 Two candidate topologies

**Topology A — Partner hosts the tunnel (literal reading of the epic).**
The law firm deploys `cloudflared` + an MCP server in *their* network, pointed at a tunnel owned by *ReloPass's* Anthropic workspace (Claude only routes to tunnels owned by your org). ReloPass's agent calls it.
- ➖ Requires each partner to deploy and operate tunnel infra and hold a ReloPass-issued tunnel token. Most immigration law firms will not do this.

**Topology B — ReloPass hosts an MCP server that wraps the partner API (recommended).**
ReloPass runs an MCP server inside the ReloPass perimeter that exposes the AIQ-379b tool surface; internally it calls the partner's real API via the `LivePartnerAdapter` (379e) over whatever channel the partner offers (REST+OAuth, mTLS, VPN). That MCP server is exposed to ReloPass's own Claude agent via an MCP Tunnel.
- ➕ No partner-side tunnel infra. Partner integration stays a normal API-client problem (the adapter). Tunnel keeps *ReloPass's* MCP server private. Reuses 379b–d untouched.
- ➕ Satisfies "without public API exposure": neither the partner API nor ReloPass's MCP server is on the public internet.

**Recommendation: Topology B.** It decouples "secure private access for the agent" (tunnel around ReloPass's MCP server) from "talk to the partner" (a conventional adapter), which is the only part that varies per partner.

---

## 2. Proposed agent tool surface

Grounded in `public.immigration_milestones` (`supabase/migrations/20260518120000_immigration_core_tables.sql §4`). The tool surface must map **1:1** onto that table so the sync service (379d) is a pure translation.

**Target enums (must be the contract's canonical vocabulary):**
- `milestone_type`: `preflight_check · dossier_assembly · criminal_record_ordered · application_filed · biometric_appointment · visa_decision · visa_issued · arrival · local_registration · work_permit_issued · permit_renewal_reminder`
- `status`: `pending · in_progress · completed · blocked · not_applicable`
- carry-through fields: `target_date`, `completed_date`, `notes`, `evidence_url`, `sort_order`, `book_early_alert`

**Tools (the MCP server / `PartnerAdapter` exposes these):**

| Tool | Signature | Returns |
|---|---|---|
| `get_case_status` | `(partner_ref: str)` | `CaseStatus { stage, milestones[], updated_at }` |
| `list_milestones` | `(partner_ref: str)` | `Milestone[]` |
| `get_milestone_evidence` | `(partner_ref: str, milestone_type: str)` | `{ evidence_url }` (optional; for visa scans etc.) |

```jsonc
// CaseStatus (canonical — see AIQ-379b for the authoritative schema)
{
  "partner_ref": "FRAGOMEN-2026-00481",
  "stage": "application_filed",          // == current milestone_type
  "updated_at": "2026-06-05T09:12:00Z",
  "milestones": [
    {
      "milestone_type": "application_filed",   // ∈ immigration_milestones.milestone_type
      "status": "completed",                   // ∈ immigration_milestones.status
      "target_date": "2026-06-01",
      "completed_date": "2026-06-02",
      "notes": "Filed at Munich Ausländerbehörde",
      "evidence_url": null
    }
  ]
}
```

- **`partner_ref`** is the partner's own case identifier; ReloPass stores it against the ReloPass `case_id` (in `immigration_cases`/case metadata) so the sync can join partner → case.
- The adapter is responsible for mapping **partner-specific milestone codes → our `milestone_type` enum**. Unmappable partner states map to `notes` + nearest enum value, never silently dropped (flag in `notes`). This mapping table lives with the `LivePartnerAdapter` (379e), not in the contract.

---

## 3. Security & PII model

Immigration data is **GDPR Article 9 special-category** (criminal-record status, biometric appointments, health-adjacent permit grounds). The model layers tunnel security (§1) with ReloPass-side controls:

- **Transport:** the three tunnel layers (outer mTLS + IP validation, inner TLS, per-server OAuth). Request **Zero Data Retention** eligibility for the workspace given Art. 9 content.
- **Write path:** the sync service writes to `immigration_milestones` as **`service_role`** (the table has an `immigration_milestones_service_role` policy = full access; the `authenticated` policies are scoped via `case_assignments`). Service-role usage stays backend-only — never exposed to the frontend bundle (per CLAUDE.md RLS rules).
- **Audit:** every status transition writes one audit row via `audit_log_service.insert_audit_log` + `set_audit_actor_context(conn, actor_type="immigration_partner_sync", ...)`. Reads of partner data should also append to the existing `data_access_log` table (created in the same migration). Consent posture is tracked in the append-only `consent_records` ledger — confirm partner data-sharing is covered by an existing consent basis before the live path goes on.
- **Credentials — three distinct high-value secrets, all env/secret-store, never committed:**
  1. Partner API OAuth / bearer credentials (consumed by `LivePartnerAdapter`).
  2. Tunnel token (Console).
  3. Proxy TLS private key + server certificate (manage renewal before expiry).
  Per Anthropic's shared-responsibility model, **token + TLS key together** would let an attacker impersonate the proxy — store them separately, rotate, and follow WIF for setup auth to avoid long-lived static tokens.
- **Blast radius:** Topology B keeps the partner API and ReloPass's MCP server off the public internet; a leaked tunnel token alone cannot read payloads without a TLS key.

---

## 4. Sync strategy — decision matrix + recommendation

The trigger that drives a sync is **orthogonal** to the tunnel transport. The sync service (379d) is identical across all three; only what *invokes* it changes.

| Strategy | Latency | Cost | Partner requirement | Needs MCP Tunnel? | Notes |
|---|---|---|---|---|---|
| **A. On-demand agent tool-call** | On case view / agent reasoning | Per call | Read API | **Yes** (agent → MCP server) | Powers HR "refresh now" and agentic monitoring (AIQ-378 Dreaming). Freshness only when looked at. |
| **B. Scheduled poll** (baseline) | = poll interval (e.g. 1–6 h) | Predictable, bounded | Read API | **No** if partner API is internet-reachable (mTLS/IP-allowlist); **Yes** if private-only | Proactive timeline freshness independent of partner push capability. Just an authenticated HTTPS client = the adapter. |
| **C. Partner push / webhook** | Seconds | Lowest | Partner must emit webhooks + we expose an inbound endpoint | No | Best latency/cost, but most law firms won't support it. Opportunistic. |

**Recommendation — layered:**
1. **Baseline: B (scheduled poll)** via the `LivePartnerAdapter` → 379d sync. Gives "real-time-ish" timeline freshness for every partner that exposes a read API, with predictable cost and no dependency on partner push features.
2. **A (on-demand agent tool-call)** for the HR "refresh now" button and for the agentic proactive-monitoring loop (AIQ-378) — this is where the **MCP Tunnel earns its keep**: it lets the Claude agent call the partner/ReloPass MCP server securely without public exposure.
3. **C (webhook)** as an opportunistic upgrade per-partner, collapsing the staleness window to ~0 when supported.

**Consequence for 379e scope:** provision the MCP Tunnel (Topology B) so strategies A and the agentic path work; but the baseline poll (B) can ship the moment a partner read-API + credentials exist, even before tunnel access is granted. Sequence: poll-first (value early), tunnel-second (agentic + private-only partners).

---

## 5. Open decisions for Romain

1. **Topology A vs B** — recommend B (ReloPass-hosted MCP server). Confirm.
2. **Tunnel timing** — ship baseline poll (B) before tunnel access is granted, or wait for the tunnel and do it all at once? Recommend poll-first.
3. **Where `partner_ref` lives** — add a `partner_ref` column to `immigration_cases` (needs a migration with RLS + REVOKE anon per CLAUDE.md), vs. stash in existing case metadata JSON. Recommend a typed column.
4. **ZDR / DPA** — confirm Zero Data Retention is requested and the partner data-sharing consent basis is recorded in `consent_records` before the live path (379e) is enabled.

---

## 6. Sources

- [MCP tunnels — Claude API Docs (platform.claude.com)](https://platform.claude.com/docs/en/agents-and-tools/mcp-tunnels/overview)
- [Anthropic Introduces MCP Tunnels for Private Agent Access — InfoQ](https://www.infoq.com/news/2026/05/claude-mcp-tunnels/)
- [Anthropic enhances Claude Managed Agents with two new privacy and security features — 9to5Mac](https://9to5mac.com/2026/05/19/anthropic-enhances-claude-managed-agents-with-two-new-privacy-and-security-features/)
- [Anthropic debuts MCP tunnels and self-hosted sandboxes — The New Stack](https://thenewstack.io/anthropic-mcp-tunnels-sandboxes/)
- In-repo: `supabase/migrations/20260518120000_immigration_core_tables.sql §4` (immigration_milestones), `backend/app/routers/immigration_status.py`, `backend/app/services/audit_log_service.py`

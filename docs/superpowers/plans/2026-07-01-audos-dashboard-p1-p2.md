# Audos Dashboard — Lead CRM (P1) + Marketing Analytics (P2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a person-level Lead CRM at `/admin/leads` fed by the live demo forms, and a pre-signup Marketing/Acquisition funnel dashboard at `/admin/marketing-analytics`, as targeted extensions of existing infrastructure.

**Architecture:** Two independent, separately-shippable slices. **P1** adds a `leads` table (ORM via `SessionLocal`, exactly like `admin_prospects`), a public rate-limited capture endpoint, an admin CRUD router, and an admin page modeled on `AdminProspects.tsx`. **P2** writes three server-side funnel events into the existing `analytics_events` table (`landing_page_view → landing_cta_click → lead_captured`), then aggregates them in a new admin router modeled on `admin_workflow_analytics.py`, rendered with the repo's hand-rolled `MetricTimeSeriesChart` (no charting dependency).

**Tech Stack:** FastAPI + SQLAlchemy ORM (`backend/app/`), Supabase/Postgres with RLS, slowapi rate limiting, React + TypeScript + Vite, antigravity component library, PostHog + server-side `analytics_events`.

## Global Constraints

- **Dual router registration (hard rule):** every new router MUST be registered in **both** `backend/main.py` (aliased single import + `app.include_router(X_router.router, ...)`) AND `backend/app/main.py` (grouped `from .routers import (...)` + `app.include_router(X.router, ...)`). Prod boots `uvicorn backend.main:app`; a router only in `app/main.py` returns 405 in prod. Verify each with the route one-liner.
- **New-table security gate (hard, all three or reject):** `ALTER TABLE ... ENABLE ROW LEVEL SECURITY;` + at least one policy + `REVOKE ALL ... FROM anon;`.
- **Migration discipline:** never auto-apply; commit an idempotent migration file with a timestamp `>` the true dir max. Apply out-of-band, then reconcile the ledger.
- **Auth deps:** admin routers use `from ..auth_deps import require_admin` + `Depends(require_admin)`. Tests override `backend.app.auth_deps.get_current_user` (NOT `backend.main`'s shadow), with `RELOPASS_QUERY_COUNTER_OFF=1`.
- **Service tree:** any new service module goes under `backend/app/services/` only.
- **No new frontend deps:** `package.json` must be unchanged. Reuse antigravity + hand-rolled SVG chart.
- **Frontend validation is `tsc --noEmit` + `npm run build`, not vitest** — importing `api/client.ts` transitively imports `api/supabase.ts`, which throws under jsdom ("supabaseUrl required"). Do not add component/unit tests that import the client.
- **PII:** if any lead free-text (`message`) is ever sent to an LLM, it must pass `mask_pii()` (`backend/app/services/pii_masker.py:203`) first. No LLM call in this build — leave a code comment only.
- **Design system:** navy `#0b2b43` / accent teal; reuse antigravity `Badge`/`Button`/`Card`. No new colors.

---

# PART 1 — Lead CRM (branch `feat/lead-crm`, one PR)

## Task 1: `leads` table migration

**Files:**
- Create: `supabase/migrations/<TS>_create_leads_table.sql` (compute `<TS>`: run `git ls-tree origin/main supabase/migrations | awk '{print $4}' | sort | tail -1`, take the leading 14-digit timestamp, and pick any value strictly greater — e.g. `20260701120000`).

**Interfaces:**
- Produces: table `public.leads` with columns consumed by Tasks 2–6.

- [ ] **Step 1: Write the migration (idempotent, security gate satisfied)**

```sql
-- Person-level inbound lead CRM (GTM-internal). No company_id tenant scoping
-- (not customer/tenant data), but RLS is still mandatory per the repo hard gate.
CREATE TABLE IF NOT EXISTS public.leads (
    id             text PRIMARY KEY,
    email          text NOT NULL,
    first_name     text,
    last_name      text,
    company_domain text,            -- FK-by-value to prospect_candidates.company_domain
    source         text NOT NULL DEFAULT 'marketing_site',  -- marketing_site | manual | referral
    status         text NOT NULL DEFAULT 'new',             -- new|contacted|qualified|converted|lost
    tags           jsonb NOT NULL DEFAULT '[]'::jsonb,       -- JSON array; SQLAlchemy generic JSON (jsonb on PG, TEXT on SQLite test env)
    message        text,
    utm_source     text,
    utm_campaign   text,
    created_at     timestamptz NOT NULL DEFAULT now(),
    updated_at     timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_leads_email          ON public.leads (email);
CREATE INDEX IF NOT EXISTS idx_leads_status         ON public.leads (status);
CREATE INDEX IF NOT EXISTS idx_leads_company_domain ON public.leads (company_domain);
CREATE INDEX IF NOT EXISTS idx_leads_created_at     ON public.leads (created_at DESC);

-- Security gate (all three mandatory)
ALTER TABLE public.leads ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "leads admin all" ON public.leads;
CREATE POLICY "leads admin all" ON public.leads
    FOR ALL USING (is_admin()) WITH CHECK (is_admin());

REVOKE ALL ON public.leads FROM anon;
```

- [ ] **Step 2: Validate the migration in a rollback transaction (no persistent change)**

Run via Supabase MCP `execute_sql` (per the repo's `reference_migration_validation_rollback` pattern) — wrap the DDL above, then assert RLS is on and anon has no grants, then `RAISE EXCEPTION 'ALL_TESTS_PASSED'` to roll back:

```sql
BEGIN;
-- (paste the CREATE TABLE + ALTER + POLICY + REVOKE from Step 1)
DO $$
BEGIN
  IF NOT (SELECT relrowsecurity FROM pg_class WHERE relname='leads') THEN
    RAISE EXCEPTION 'RLS_NOT_ENABLED';
  END IF;
  IF EXISTS (
    SELECT 1 FROM information_schema.role_table_grants
    WHERE table_name='leads' AND grantee='anon'
  ) THEN RAISE EXCEPTION 'ANON_STILL_GRANTED'; END IF;
  RAISE EXCEPTION 'ALL_TESTS_PASSED';
END $$;
ROLLBACK;
```
Expected: the call fails with `ALL_TESTS_PASSED` (proves asserts passed and nothing persisted).

- [ ] **Step 3: Commit the migration file** (application to prod + ledger reconciliation happens out-of-band per Global Constraints — note it in the PR description).

```bash
git add supabase/migrations/<TS>_create_leads_table.sql
git commit -m "feat(leads): [audos-P1] create leads table with RLS (admin-only)"
```

---

## Task 2: `Lead` ORM model + Pydantic schemas

**Files:**
- Modify: `backend/app/models.py` (append a `Lead` class after `ProspectCandidate`, ~line 383)
- Create: `backend/app/routers/_leads_schemas.py` (shared Pydantic models for Tasks 3 & 4)

**Interfaces:**
- Produces: `Lead` (ORM, `__tablename__="leads"`); `LeadOut`, `LeadCaptureIn`, `LeadPatchIn`, `LeadStatsOut` (Pydantic).

- [ ] **Step 1: Add the ORM model** to `backend/app/models.py` (mirrors `ProspectCandidate` style — `String` PK, app-generated uuid; add `JSON` to the existing `from sqlalchemy import ...` line at the top of the file. Use the generic `JSON` type — NOT `ARRAY` — so the model works on both Postgres (jsonb) and the SQLite test harness):

```python
class Lead(Base):
    """Person-level inbound lead (GTM-internal CRM). Fed by the public
    lead-capture endpoint (marketing-site demo forms) and manual entry.
    company_domain is an FK-by-value to prospect_candidates.company_domain
    so inbound leads can be matched against the outbound pipeline."""

    __tablename__ = "leads"

    id = Column(String, primary_key=True, index=True)
    email = Column(String, nullable=False, index=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    company_domain = Column(String, nullable=True, index=True)
    source = Column(String, nullable=False, default="marketing_site")
    status = Column(String, nullable=False, default="new", index=True)
    tags = Column(JSON, nullable=False, default=list)  # generic JSON (jsonb on PG, TEXT on SQLite)
    message = Column(Text, nullable=True)
    utm_source = Column(String, nullable=True)
    utm_campaign = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
```

- [ ] **Step 2: Create the shared schemas** at `backend/app/routers/_leads_schemas.py`:

```python
from __future__ import annotations

from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field

VALID_STATUSES = {"new", "contacted", "qualified", "converted", "lost"}
VALID_SOURCES = {"marketing_site", "manual", "referral"}


class LeadCaptureIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr
    first_name: Optional[str] = Field(None, max_length=200)
    last_name: Optional[str] = Field(None, max_length=200)
    company_domain: Optional[str] = Field(None, max_length=300)
    message: Optional[str] = Field(None, max_length=2000)
    source: str = Field("marketing_site", max_length=50)
    utm_source: Optional[str] = Field(None, max_length=200)
    utm_campaign: Optional[str] = Field(None, max_length=200)


class LeadPatchIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Optional[str] = Field(None)
    tags: Optional[List[str]] = None


class LeadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    email: str
    first_name: Optional[str]
    last_name: Optional[str]
    company_domain: Optional[str]
    source: str
    status: str
    tags: List[str]
    message: Optional[str]
    utm_source: Optional[str]
    utm_campaign: Optional[str]
    created_at: Any
    updated_at: Any
    matched_prospect: bool = False


class LeadStatsOut(BaseModel):
    total: int
    new_this_week: int
    by_status: dict
```

- [ ] **Step 3: Type-check & commit**

Run: `cd frontend && npx tsc --noEmit` is N/A here; instead `cd /Users/romainlecomte/Documents/GitHub/rolec && python3 -c "from backend.app.models import Lead; from backend.app.routers._leads_schemas import LeadOut; print('ok')"`
Expected: prints `ok`.

```bash
git add backend/app/models.py backend/app/routers/_leads_schemas.py
git commit -m "feat(leads): [audos-P1] Lead ORM model + request/response schemas"
```

---

## Task 3: Admin CRUD router (`admin_leads`)

**Files:**
- Create: `backend/app/routers/admin_leads.py`
- Modify: `backend/main.py` (import ~line 163 block; `include_router` ~line 804 block)
- Modify: `backend/app/main.py` (grouped import ~line 12; `include_router` ~line 171)
- Test: `backend/tests/test_admin_leads.py`

**Interfaces:**
- Consumes: `Lead` (Task 2), `require_admin` (`backend/app/auth_deps.py`), `SessionLocal` (`backend/app/db.py`).
- Produces: `GET /api/admin/leads`, `GET /api/admin/leads/stats`, `GET /api/admin/leads/{id}`, `PATCH /api/admin/leads/{id}`.

- [ ] **Step 1: Write the failing test** at `backend/tests/test_admin_leads.py` (app-mounted harness; override `get_current_user` from `auth_deps`):

```python
import os
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")
os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")

import uuid
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.app import auth_deps
from backend.app.db import Base, SessionLocal, engine
from backend.app.models import Lead

# The SQLite test harness may not have run init_db(); ensure ORM tables exist.
Base.metadata.create_all(bind=engine)


@pytest.fixture
def admin_client():
    app.dependency_overrides[auth_deps.get_current_user] = lambda: {
        "id": "admin-1", "email": "admin@relopass.com", "role": "ADMIN",
    }
    yield TestClient(app)
    app.dependency_overrides.clear()


def _seed_lead(**kw):
    s = SessionLocal()
    lead = Lead(id=str(uuid.uuid4()), email=kw.get("email", "a@b.com"),
                company_domain=kw.get("company_domain"), status=kw.get("status", "new"),
                source="marketing_site", tags=[])
    s.add(lead); s.commit(); lid = lead.id; s.close()
    return lid


def test_list_leads_returns_seeded(admin_client):
    lid = _seed_lead(email="lister@acme.com")
    r = admin_client.get("/api/admin/leads")
    assert r.status_code == 200
    assert any(row["id"] == lid for row in r.json()["leads"])


def test_patch_lead_status(admin_client):
    lid = _seed_lead(email="patch@acme.com")
    r = admin_client.patch(f"/api/admin/leads/{lid}", json={"status": "qualified"})
    assert r.status_code == 200
    assert r.json()["status"] == "qualified"


def test_patch_rejects_bad_status(admin_client):
    lid = _seed_lead(email="bad@acme.com")
    r = admin_client.patch(f"/api/admin/leads/{lid}", json={"status": "banana"})
    assert r.status_code == 422 or r.status_code == 400


def test_stats_shape(admin_client):
    _seed_lead(email="stat@acme.com")
    r = admin_client.get("/api/admin/leads/stats")
    assert r.status_code == 200
    body = r.json()
    assert "total" in body and "new_this_week" in body and "by_status" in body
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd /Users/romainlecomte/Documents/GitHub/rolec && RELOPASS_QUERY_COUNTER_OFF=1 .venv311/bin/pytest backend/tests/test_admin_leads.py -q`
Expected: FAIL (404 / route not found — router not yet created/registered).

- [ ] **Step 3: Write the router** at `backend/app/routers/admin_leads.py`:

```python
"""Admin Lead CRM router — inbound person-level leads.
Modeled on admin_prospects.py (ORM via SessionLocal). Admin-only."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, func

from ..auth_deps import require_admin
from ..db import SessionLocal
from ..models import Lead, ProspectCandidate
from ._leads_schemas import VALID_STATUSES, LeadOut, LeadPatchIn, LeadStatsOut

router = APIRouter(prefix="/leads", tags=["admin-leads"])


def _to_out(lead: Lead, matched_domains: set) -> LeadOut:
    out = LeadOut.model_validate(lead)
    out.matched_prospect = bool(lead.company_domain and lead.company_domain in matched_domains)
    return out


@router.get("", response_model=Dict[str, Any])
def list_leads(
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=500),
    _admin: dict = Depends(require_admin),
) -> Dict[str, Any]:
    s = SessionLocal()
    try:
        q = s.query(Lead)
        if status:
            q = q.filter(Lead.status == status)
        if search:
            like = f"%{search.lower()}%"
            q = q.filter(func.lower(Lead.email).like(like))
        rows = q.order_by(desc(Lead.created_at)).limit(limit).all()
        total = s.query(func.count(Lead.id)).scalar() or 0
        domains = {d for (d,) in s.query(ProspectCandidate.company_domain)
                   .filter(ProspectCandidate.company_domain.isnot(None)).all()}
        return {"total": total, "leads": [_to_out(r, domains).model_dump() for r in rows]}
    finally:
        s.close()


@router.get("/stats", response_model=LeadStatsOut)
def lead_stats(_admin: dict = Depends(require_admin)) -> LeadStatsOut:
    s = SessionLocal()
    try:
        week_ago = datetime.now(timezone.utc) - timedelta(days=7)
        total = s.query(func.count(Lead.id)).scalar() or 0
        new_this_week = s.query(func.count(Lead.id)).filter(Lead.created_at >= week_ago).scalar() or 0
        by_status = dict(s.query(Lead.status, func.count(Lead.id)).group_by(Lead.status).all())
        return LeadStatsOut(total=total, new_this_week=new_this_week, by_status=by_status)
    finally:
        s.close()


@router.get("/{lead_id}", response_model=LeadOut)
def get_lead(lead_id: str, _admin: dict = Depends(require_admin)) -> LeadOut:
    s = SessionLocal()
    try:
        lead = s.query(Lead).filter(Lead.id == lead_id).first()
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")
        domains = {d for (d,) in s.query(ProspectCandidate.company_domain)
                   .filter(ProspectCandidate.company_domain == lead.company_domain).all()}
        return _to_out(lead, domains)
    finally:
        s.close()


@router.patch("/{lead_id}", response_model=LeadOut)
def patch_lead(lead_id: str, body: LeadPatchIn, _admin: dict = Depends(require_admin)) -> LeadOut:
    if body.status is not None and body.status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status: {body.status}")
    s = SessionLocal()
    try:
        lead = s.query(Lead).filter(Lead.id == lead_id).first()
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")
        if body.status is not None:
            lead.status = body.status
        if body.tags is not None:
            lead.tags = body.tags
        s.commit()
        s.refresh(lead)
        return _to_out(lead, set())
    finally:
        s.close()
```

- [ ] **Step 4: Register in BOTH mains.** In `backend/main.py` add next to the other `from .app.routers import ... as ..._router` lines (~163) and the `include_router` block (~804):

```python
from .app.routers import admin_leads as admin_leads_router          # ~line 163
app.include_router(admin_leads_router.router, prefix="/api/admin")   # ~line 804
```
In `backend/app/main.py` add `admin_leads` to the grouped `from .routers import ( ... )` block (~line 12) and, next to the other admin includes (~line 171):

```python
app.include_router(admin_leads.router, prefix="/api/admin")
```

- [ ] **Step 5: Verify route is live on the prod app instance**

Run: `cd /Users/romainlecomte/Documents/GitHub/rolec && python3 -c "from backend.main import app; print(sorted(r.path for r in app.routes if 'lead' in r.path))"`
Expected: includes `/api/admin/leads`, `/api/admin/leads/stats`, `/api/admin/leads/{lead_id}`.

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd /Users/romainlecomte/Documents/GitHub/rolec && RELOPASS_QUERY_COUNTER_OFF=1 .venv311/bin/pytest backend/tests/test_admin_leads.py -q`
Expected: 4 passed.

- [ ] **Step 7: Commit**

```bash
git add backend/app/routers/admin_leads.py backend/main.py backend/app/main.py backend/tests/test_admin_leads.py
git commit -m "feat(leads): [audos-P1] admin CRUD router (list/get/patch/stats), dual-registered"
```

---

## Task 4: Public lead-capture endpoint (rate-limited)

**Files:**
- Create: `backend/app/routers/lead_capture.py`
- Modify: `backend/main.py` + `backend/app/main.py` (register WITHOUT `/api/admin` prefix — the router carries its own `/api/public` path)
- Test: `backend/tests/test_lead_capture.py`

**Interfaces:**
- Consumes: `Lead` (Task 2), `LeadCaptureIn` (Task 2), `limiter` (`backend/rate_limit.py`), `emit_event` (`backend/app/services/analytics_service.py`).
- Produces: `POST /api/public/lead-capture` → `{"id": <str>, "matched_prospect": <bool>}`; server-side emits `lead_captured` into `analytics_events` (consumed by P2 Task 10).

- [ ] **Step 1: Write the failing test** at `backend/tests/test_lead_capture.py`:

```python
import os
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")
os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")

from fastapi.testclient import TestClient
from backend.main import app
from backend.app.db import Base, engine

Base.metadata.create_all(bind=engine)  # ensure leads table exists on SQLite harness

client = TestClient(app)


def test_capture_creates_lead_and_derives_domain():
    r = client.post("/api/public/lead-capture", json={
        "email": "jane@acme.com", "first_name": "Jane", "source": "marketing_site",
        "utm_source": "google", "utm_campaign": "brand",
    })
    assert r.status_code == 201, r.text
    assert r.json()["id"]


def test_capture_rejects_bad_email():
    r = client.post("/api/public/lead-capture", json={"email": "not-an-email"})
    assert r.status_code == 422
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd /Users/romainlecomte/Documents/GitHub/rolec && RELOPASS_DISABLE_RATE_LIMITS=1 RELOPASS_QUERY_COUNTER_OFF=1 .venv311/bin/pytest backend/tests/test_lead_capture.py -q`
Expected: FAIL (404 — route not registered).

- [ ] **Step 3: Write the router** at `backend/app/routers/lead_capture.py` (public; slowapi requires the `request: Request` param and decorator order `@router.post` then `@limiter.limit`):

```python
"""Public, unauthenticated, rate-limited lead capture.
Fed by the marketing-site demo forms. Writes a person-level lead and
emits a `lead_captured` analytics event (bottom of the marketing funnel).

PII: `message` is stored raw for GTM. If a future ticket routes it to an
LLM for enrichment, it MUST pass mask_pii() first (repo data-minimisation rule)."""
from __future__ import annotations

import logging
import uuid
from typing import Any, Dict

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ...rate_limit import limiter
from ..db import SessionLocal
from ..models import Lead, ProspectCandidate
from ..services.analytics_service import emit_event
from ._leads_schemas import LeadCaptureIn

log = logging.getLogger(__name__)
router = APIRouter(tags=["public-lead-capture"])


def _domain_from_email(email: str) -> str | None:
    return email.split("@", 1)[1].lower() if "@" in email else None


@router.post("/api/public/lead-capture", status_code=201)
@limiter.limit("10/hour;50/day")
def capture_lead(body: LeadCaptureIn, request: Request) -> JSONResponse:
    domain = body.company_domain or _domain_from_email(str(body.email))
    lead_id = str(uuid.uuid4())
    matched = False
    s = SessionLocal()
    try:
        lead = Lead(
            id=lead_id, email=str(body.email), first_name=body.first_name,
            last_name=body.last_name, company_domain=domain, source=body.source,
            status="new", tags=[], message=body.message,
            utm_source=body.utm_source, utm_campaign=body.utm_campaign,
        )
        s.add(lead)
        s.commit()
        if domain:
            matched = s.query(ProspectCandidate.id).filter(
                ProspectCandidate.company_domain == domain).first() is not None
    finally:
        s.close()
    # Bottom-of-funnel event → analytics_events (consumed by marketing dashboard)
    emit_event("lead_captured", extra={
        "source": body.source, "utm_source": body.utm_source,
        "utm_campaign": body.utm_campaign, "matched_prospect": matched,
    })
    return JSONResponse(status_code=201, content={"id": lead_id, "matched_prospect": matched})
```

- [ ] **Step 4: Register in BOTH mains (no `/api/admin` prefix).** `backend/main.py`:

```python
from .app.routers import lead_capture as lead_capture_router   # ~line 163 block
app.include_router(lead_capture_router.router)                 # ~line 804 block
```
`backend/app/main.py`: add `lead_capture` to the grouped import and `app.include_router(lead_capture.router)` (no prefix).

- [ ] **Step 5: Verify route + run tests**

Run: `cd /Users/romainlecomte/Documents/GitHub/rolec && python3 -c "from backend.main import app; print([r.path for r in app.routes if 'public/lead' in r.path])"`
Expected: `['/api/public/lead-capture']`.
Run: `RELOPASS_DISABLE_RATE_LIMITS=1 RELOPASS_QUERY_COUNTER_OFF=1 .venv311/bin/pytest backend/tests/test_lead_capture.py -q`
Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/lead_capture.py backend/main.py backend/app/main.py backend/tests/test_lead_capture.py
git commit -m "feat(leads): [audos-P1] public rate-limited lead-capture endpoint + lead_captured event"
```

---

## Task 5: Frontend API client (`adminLeadsAPI` + `leadCaptureAPI`)

**Files:**
- Modify: `frontend/src/api/client.ts` (add types + two API objects near `adminProspectsAPI`, ~line 1879)

**Interfaces:**
- Produces: `adminLeadsAPI.{list,get,patch,stats}`, `leadCaptureAPI.submit`, types `LeadRow`, `LeadStats`.

- [ ] **Step 1: Add types + API objects** to `frontend/src/api/client.ts`:

```ts
export interface LeadRow {
  id: string;
  email: string;
  first_name: string | null;
  last_name: string | null;
  company_domain: string | null;
  source: string;
  status: string;
  tags: string[];
  message: string | null;
  utm_source: string | null;
  utm_campaign: string | null;
  created_at: string;
  updated_at: string;
  matched_prospect: boolean;
}

export interface LeadStats {
  total: number;
  new_this_week: number;
  by_status: Record<string, number>;
}

export const adminLeadsAPI = {
  list: async (params?: { status?: string; search?: string; limit?: number }) =>
    api
      .get('/api/admin/leads', { params: params || {} })
      .then((r) => r.data as { total: number; leads: LeadRow[] }),
  get: async (id: string) =>
    api.get(`/api/admin/leads/${id}`).then((r) => r.data as LeadRow),
  patch: async (id: string, patch: { status?: string; tags?: string[] }) =>
    api.patch(`/api/admin/leads/${id}`, patch).then((r) => r.data as LeadRow),
  stats: async () => api.get('/api/admin/leads/stats').then((r) => r.data as LeadStats),
};

export const leadCaptureAPI = {
  submit: async (payload: {
    email: string; first_name?: string; last_name?: string;
    company_domain?: string; message?: string; source: string;
    utm_source?: string; utm_campaign?: string;
  }) =>
    api.post('/api/public/lead-capture', payload).then((r) => r.data as { id: string; matched_prospect: boolean }),
};
```

- [ ] **Step 2: Type-check & commit**

Run: `cd frontend && npx tsc --noEmit`
Expected: clean (no errors).

```bash
git add frontend/src/api/client.ts
git commit -m "feat(leads): [audos-P1] adminLeadsAPI + leadCaptureAPI client wrappers"
```

---

## Task 6: Admin Leads page + route

**Files:**
- Create: `frontend/src/pages/admin/AdminLeads.tsx` (modeled on `AdminProspects.tsx`)
- Modify: `frontend/src/navigation/routes.ts` (add `adminLeads` entry near line 142)
- Modify: `frontend/src/App.tsx` (lazy import ~line 141; `<Route>` ~line 414)

**Interfaces:**
- Consumes: `adminLeadsAPI`, `LeadRow` (Task 5); `Badge`/`Button`/`Card` (antigravity); `AdminLayout`, `RefreshButton`.

- [ ] **Step 1: Add the route definition** to `frontend/src/navigation/routes.ts` (after the `adminProspects` line):

```ts
adminLeads: { path: '/admin/leads', roles: ['ADMIN'] as RouteRole[] },
```

- [ ] **Step 2: Create the page** at `frontend/src/pages/admin/AdminLeads.tsx`:

```tsx
import React, { useCallback, useEffect, useState } from 'react';
import { Alert, Badge, Button, Card } from '../../components/antigravity';
import { RefreshButton } from '../../components/RefreshButton';
import { adminLeadsAPI, type LeadRow } from '../../api/client';
import { AdminLayout } from './AdminLayout';

const STATUS_FILTERS: { value: string; label: string }[] = [
  { value: '', label: 'All' },
  { value: 'new', label: 'New' },
  { value: 'contacted', label: 'Contacted' },
  { value: 'qualified', label: 'Qualified' },
  { value: 'converted', label: 'Converted' },
  { value: 'lost', label: 'Lost' },
];

const NEXT_STATUS: Record<string, string> = {
  new: 'contacted', contacted: 'qualified', qualified: 'converted',
};

function statusBadge(status: string): React.ReactElement {
  const variant =
    status === 'converted' ? 'success'
    : status === 'qualified' ? 'info'
    : status === 'lost' ? 'error'
    : status === 'contacted' ? 'warning'
    : 'info';
  return <Badge variant={variant}>{status}</Badge>;
}

export const AdminLeads: React.FC = () => {
  const [rows, setRows] = useState<LeadRow[]>([]);
  const [total, setTotal] = useState(0);
  const [statusFilter, setStatusFilter] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params: { status?: string; limit: number } = { limit: 200 };
      if (statusFilter) params.status = statusFilter;
      const res = await adminLeadsAPI.list(params);
      setRows(res.leads);
      setTotal(res.total);
    } catch (err: unknown) {
      const msg =
        err && typeof err === 'object' && 'response' in err
          ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : (err as Error)?.message;
      setError(String(msg || 'Failed to load leads'));
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => { void load(); }, [load]);

  const advance = async (r: LeadRow) => {
    const next = NEXT_STATUS[r.status];
    if (!next) return;
    await adminLeadsAPI.patch(r.id, { status: next });
    void load();
  };

  return (
    <AdminLayout title="Leads" subtitle="Inbound marketing-site leads and pipeline triage">
      <Card>
        <div className="flex items-center gap-2 mb-4 flex-wrap">
          {STATUS_FILTERS.map((f) => (
            <Button
              key={f.value || 'all'}
              variant={statusFilter === f.value ? 'primary' : 'outline'}
              size="sm"
              onClick={() => setStatusFilter(f.value)}
            >
              {f.label}
            </Button>
          ))}
          <div className="ml-auto flex items-center gap-2">
            <span className="text-xs text-[#6b7280]">{total} total</span>
            <RefreshButton onClick={() => void load()} loading={loading} />
          </div>
        </div>
        {error && <Alert variant="error">{error}</Alert>}
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-[#6b7280] border-b border-[#e5e7eb]">
              <th className="py-2 pr-3">Email</th>
              <th className="py-2 pr-3">Company</th>
              <th className="py-2 pr-3">Source</th>
              <th className="py-2 pr-3">Status</th>
              <th className="py-2 pr-3">Match</th>
              <th className="py-2">Action</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id} className="border-b border-[#f3f4f6] hover:bg-[#f8fafc]">
                <td className="py-2 pr-3 font-medium text-[#0b2b43]">{r.email}</td>
                <td className="py-2 pr-3 text-[#374151]">{r.company_domain || '—'}</td>
                <td className="py-2 pr-3 text-[#374151]">{r.source}</td>
                <td className="py-2 pr-3">{statusBadge(r.status)}</td>
                <td className="py-2 pr-3">
                  {r.matched_prospect ? <Badge variant="success">matched prospect</Badge> : '—'}
                </td>
                <td className="py-2">
                  {NEXT_STATUS[r.status] && (
                    <Button size="sm" variant="outline" onClick={() => void advance(r)}>
                      → {NEXT_STATUS[r.status]}
                    </Button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!loading && rows.length === 0 && (
          <p className="text-sm text-[#6b7280] py-6 text-center">No leads yet.</p>
        )}
      </Card>
    </AdminLayout>
  );
};
```

- [ ] **Step 3: Register the route in `frontend/src/App.tsx`** — add the lazy import next to the other admin imports (~line 141) and the `<Route>` next to `adminProspects` (~line 414):

```tsx
const AdminLeads = lazy(() => import('./pages/admin/AdminLeads').then((module) => ({ default: module.AdminLeads })));
```
```tsx
<Route path={ROUTE_DEFS.adminLeads.path} element={<RequireAdminRoute><AdminLeads /></RequireAdminRoute>} />
```
(If admin nav links are defined in a sidebar such as `PlatformShellSidebar.tsx`, add a "Leads" link there next to "Prospects" — optional, follow the existing admin-nav pattern.)

- [ ] **Step 4: Type-check + build**

Run: `cd frontend && npx tsc --noEmit && npm run build`
Expected: both clean.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/admin/AdminLeads.tsx frontend/src/navigation/routes.ts frontend/src/App.tsx
git commit -m "feat(leads): [audos-P1] AdminLeads page + /admin/leads route"
```

---

## Task 7: Wire the demo forms → capture

**Files:**
- Modify: `frontend/src/components/marketing/BookDemoModal.tsx` (~line 144, after the existing `track('demo_request_submitted', …)`)
- Modify: `frontend/src/components/marketing/InlineDemoForm.tsx` (~line 84)

**Interfaces:**
- Consumes: `leadCaptureAPI.submit` (Task 5).

- [ ] **Step 1: Add a best-effort, non-blocking capture call** in each form, immediately after the existing `track('demo_request_submitted', …)`. Use the form's existing field variables (email/name); read UTM from the URL. Example for `BookDemoModal.tsx`:

```tsx
import { leadCaptureAPI } from '../../api/client';
// ...after track('demo_request_submitted', ...):
try {
  const usp = new URLSearchParams(window.location.search);
  void leadCaptureAPI.submit({
    email,                       // existing form state var
    first_name: name || undefined,
    message: message || undefined,
    source: 'marketing_site',
    utm_source: usp.get('utm_source') || undefined,
    utm_campaign: usp.get('utm_campaign') || undefined,
  });
} catch {
  /* capture is best-effort; never block the demo request */
}
```
Repeat the same block in `InlineDemoForm.tsx` using its local field names. (The `void` + swallowed catch guarantees a failed capture cannot break the user's demo submission.)

- [ ] **Step 2: Type-check + build**

Run: `cd frontend && npx tsc --noEmit && npm run build`
Expected: both clean.

- [ ] **Step 3: Manual QA (staging)**

Submit the demo form on staging → confirm a row appears at `/admin/leads` within seconds; if the email domain matches an existing `prospect_candidates.company_domain`, the "matched prospect" badge shows.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/marketing/BookDemoModal.tsx frontend/src/components/marketing/InlineDemoForm.tsx
git commit -m "feat(leads): [audos-P1] wire demo forms to public lead-capture (best-effort)"
```

**→ Open PR 1 (`feat/lead-crm`). Before merge, run the full P1 validation checklist (bottom of this doc).**

---

# PART 2 — Marketing/Acquisition Analytics (branch `feat/marketing-analytics`, one PR)

> **Ingestion decision (resolves the spec's open detail):** client PostHog `track()` events do NOT reach `analytics_events`. The admin funnel dashboard reads `analytics_events` only. So we add a public `POST /api/public/track` that calls `emit_event`, and instrument `Landing.tsx` to hit it. The `lead_captured` event (P1 Task 4) already lands server-side, so the funnel is fully server-written: `landing_page_view → landing_cta_click → lead_captured`.

## Task 8: Public analytics track endpoint

**Files:**
- Create: `backend/app/routers/public_analytics.py`
- Modify: `backend/main.py` + `backend/app/main.py` (register, no `/api/admin` prefix)
- Test: `backend/tests/test_public_track.py`

**Interfaces:**
- Consumes: `limiter`, `emit_event`.
- Produces: `POST /api/public/track` → `{"ok": true}`; writes `event_name` into `analytics_events`.

- [ ] **Step 1: Write the failing test** at `backend/tests/test_public_track.py`:

```python
import os
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")
os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")

from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)


def test_track_accepts_allowed_event():
    r = client.post("/api/public/track", json={
        "event": "landing_page_view", "properties": {"utm_source": "google"},
    })
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_track_rejects_unknown_event():
    r = client.post("/api/public/track", json={"event": "arbitrary_event"})
    assert r.status_code == 422 or r.status_code == 400
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd /Users/romainlecomte/Documents/GitHub/rolec && RELOPASS_DISABLE_RATE_LIMITS=1 RELOPASS_QUERY_COUNTER_OFF=1 .venv311/bin/pytest backend/tests/test_public_track.py -q`
Expected: FAIL (404).

- [ ] **Step 3: Write the router** at `backend/app/routers/public_analytics.py` (allow-list the event names so this public endpoint can't pollute `analytics_events` with arbitrary strings):

```python
"""Public, rate-limited marketing funnel event ingestion.
Writes an allow-listed marketing event into analytics_events so the admin
marketing dashboard can aggregate it. PostHog remains the product-analytics
sink; this path exists only to feed the server-side funnel."""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from ...rate_limit import limiter
from ..services.analytics_service import emit_event

router = APIRouter(tags=["public-analytics"])

ALLOWED_MARKETING_EVENTS = {"landing_page_view", "landing_cta_click"}


class TrackIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event: str = Field(..., max_length=100)
    properties: Optional[Dict[str, Any]] = None


@router.post("/api/public/track")
@limiter.limit("120/hour;1000/day")
def track_event(body: TrackIn, request: Request) -> Dict[str, Any]:
    if body.event not in ALLOWED_MARKETING_EVENTS:
        raise HTTPException(status_code=400, detail="Unknown event")
    props = body.properties or {}
    # Only scalar allow-listed keys — no free-text/PII from the public web.
    safe = {k: props.get(k) for k in ("utm_source", "utm_campaign", "cta", "source")}
    emit_event(body.event, extra=safe)
    return {"ok": True}
```

- [ ] **Step 4: Register in BOTH mains** (no prefix), same as Task 4:

```python
from .app.routers import public_analytics as public_analytics_router   # backend/main.py ~163
app.include_router(public_analytics_router.router)                     # backend/main.py ~804
```
`backend/app/main.py`: grouped import + `app.include_router(public_analytics.router)`.

- [ ] **Step 5: Verify route + run tests**

Run: `python3 -c "from backend.main import app; print([r.path for r in app.routes if 'public/track' in r.path])"`
Expected: `['/api/public/track']`.
Run: `RELOPASS_DISABLE_RATE_LIMITS=1 RELOPASS_QUERY_COUNTER_OFF=1 .venv311/bin/pytest backend/tests/test_public_track.py -q`
Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/public_analytics.py backend/main.py backend/app/main.py backend/tests/test_public_track.py
git commit -m "feat(marketing): [audos-P2] public rate-limited /api/public/track (allow-listed funnel events)"
```

---

## Task 9: Instrument the landing page

**Files:**
- Modify: `frontend/src/analytics.ts` (add `emitMarketingEvent` helper)
- Modify: `frontend/src/pages/Landing.tsx` (page-view on mount + CTA-click handlers)

**Interfaces:**
- Consumes: `track` (existing), `api`/`API_BASE_URL` (for the server POST).
- Produces: emits `landing_page_view` (mount) and `landing_cta_click` (each CTA) to BOTH PostHog and `/api/public/track`.

- [ ] **Step 1: Add the helper** to `frontend/src/analytics.ts` (uses `fetch` to avoid importing the axios client into this low-level module; best-effort):

```ts
/** Emit a marketing funnel event to BOTH PostHog and the server-side
 *  analytics_events sink (which the admin marketing dashboard reads). */
export function emitMarketingEvent(event: string, properties?: Record<string, unknown>): void {
  track(event, properties);
  try {
    const base = import.meta.env.VITE_API_URL || '';
    void fetch(`${base}/api/public/track`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ event, properties: properties || {} }),
      keepalive: true,
    });
  } catch {
    /* best-effort */
  }
}

/** Read utm_source / utm_campaign from the current URL. */
export function readUtm(): { utm_source?: string; utm_campaign?: string } {
  const usp = new URLSearchParams(window.location.search);
  return {
    utm_source: usp.get('utm_source') || undefined,
    utm_campaign: usp.get('utm_campaign') || undefined,
  };
}
```

- [ ] **Step 2: Emit `landing_page_view` on mount** in `frontend/src/pages/Landing.tsx` — add near the top of the component body (after the existing hooks, e.g. after line 89's `useDemoBooking`):

```tsx
import { emitMarketingEvent, readUtm } from '../analytics';
// ...inside the component:
useEffect(() => {
  emitMarketingEvent('landing_page_view', readUtm());
}, []);
```

- [ ] **Step 3: Emit `landing_cta_click` on the primary CTAs.** For the demo CTAs (hero + final), add the emit alongside the existing `openDemoBooking(...)` call; for the `to`-based link CTAs, add an `onClick` that fires the emit (the link still navigates):

```tsx
// hero primary (was: to={buildRoute('access')})
<CTAButton
  to={buildRoute('access')}
  onClick={() => emitMarketingEvent('landing_cta_click', { cta: 'hero-primary', ...readUtm() })}
  variant="primary" size="lg"
>{c.hero.primaryCta}</CTAButton>

// hero secondary (demo)
<CTAButton
  onClick={() => { emitMarketingEvent('landing_cta_click', { cta: 'hero-demo', ...readUtm() }); openDemoBooking('landing-hero'); }}
  variant="outline" size="lg"
>{c.hero.secondaryCta}</CTAButton>

// final CTA (demo)
<CTAButton
  onClick={() => { emitMarketingEvent('landing_cta_click', { cta: 'final-demo', ...readUtm() }); openDemoBooking('landing-final'); }}
  variant="primary" size="lg"
>{c.finalCta.options.demo}</CTAButton>
```

- [ ] **Step 4: Type-check + build**

Run: `cd frontend && npx tsc --noEmit && npm run build`
Expected: both clean.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/analytics.ts frontend/src/pages/Landing.tsx
git commit -m "feat(marketing): [audos-P2] instrument landing page (page_view + cta_click) to server sink"
```

---

## Task 10: Marketing analytics aggregation router

**Files:**
- Create: `backend/app/routers/admin_marketing_analytics.py` (modeled on `admin_workflow_analytics.py`)
- Modify: `backend/main.py` + `backend/app/main.py` (register with `/api/admin` prefix)
- Test: `backend/tests/test_admin_marketing_analytics.py`

**Interfaces:**
- Consumes: `db.count_analytics_events_by_name`, `db.list_analytics_events` (`backend/db/audit.py` via `from ...database import db`), `require_admin`.
- Produces: `GET /api/admin/marketing-analytics/funnel` → `{period_days, events{landing_page_view,landing_cta_click,lead_captured}, rates{cta_rate_pct,capture_rate_pct}, daily[]}`.

- [ ] **Step 1: Write the failing test** at `backend/tests/test_admin_marketing_analytics.py`:

```python
import os
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")
os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")

import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.app import auth_deps


@pytest.fixture
def admin_client():
    app.dependency_overrides[auth_deps.get_current_user] = lambda: {
        "id": "admin-1", "email": "admin@relopass.com", "role": "ADMIN",
    }
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_funnel_shape(admin_client):
    r = admin_client.get("/api/admin/marketing-analytics/funnel")
    assert r.status_code == 200
    body = r.json()
    assert set(["landing_page_view", "landing_cta_click", "lead_captured"]).issubset(body["events"].keys())
    assert "cta_rate_pct" in body["rates"] and "capture_rate_pct" in body["rates"]
    assert isinstance(body["daily"], list)
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd /Users/romainlecomte/Documents/GitHub/rolec && RELOPASS_QUERY_COUNTER_OFF=1 .venv311/bin/pytest backend/tests/test_admin_marketing_analytics.py -q`
Expected: FAIL (404).

- [ ] **Step 3: Write the router** at `backend/app/routers/admin_marketing_analytics.py`:

```python
"""Admin Marketing/Acquisition Analytics — pre-signup funnel.
Reads the same analytics_events table as admin_workflow_analytics.py.
Funnel: landing_page_view -> landing_cta_click -> lead_captured. Admin-only."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, Query

from ..auth_deps import require_admin
from ...database import db

router = APIRouter(prefix="/marketing-analytics", tags=["admin-marketing-analytics"])

FUNNEL_EVENTS = ["landing_page_view", "landing_cta_click", "lead_captured"]


def _default_since(days: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


@router.get("/funnel")
def marketing_funnel(
    days: int = Query(30, ge=1, le=90),
    _admin: dict = Depends(require_admin),
) -> Dict[str, Any]:
    since = _default_since(days)
    counts = db.count_analytics_events_by_name(since=since)
    views = counts.get("landing_page_view", 0)
    clicks = counts.get("landing_cta_click", 0)
    captured = counts.get("lead_captured", 0)

    # Daily series for the trend chart: bucket raw events by date.
    daily_map: Dict[str, Dict[str, int]] = defaultdict(lambda: {k: 0 for k in FUNNEL_EVENTS})
    for name in FUNNEL_EVENTS:
        for ev in db.list_analytics_events(event_name=name, since=since, limit=5000):
            day = str(ev.get("created_at", ""))[:10]
            if day:
                daily_map[day][name] += 1
    daily = [{"date": d, **daily_map[d]} for d in sorted(daily_map.keys())]

    return {
        "period_days": days,
        "since": since,
        "events": {"landing_page_view": views, "landing_cta_click": clicks, "lead_captured": captured},
        "rates": {
            "cta_rate_pct": round((clicks / views * 100) if views else 0, 1),
            "capture_rate_pct": round((captured / clicks * 100) if clicks else 0, 1),
        },
        "daily": daily,
    }
```

- [ ] **Step 4: Register in BOTH mains** (with `/api/admin` prefix), same pattern as Task 3.

- [ ] **Step 5: Verify route + run tests**

Run: `python3 -c "from backend.main import app; print([r.path for r in app.routes if 'marketing' in r.path])"`
Expected: `['/api/admin/marketing-analytics/funnel']`.
Run: `RELOPASS_QUERY_COUNTER_OFF=1 .venv311/bin/pytest backend/tests/test_admin_marketing_analytics.py -q`
Expected: 1 passed.

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/admin_marketing_analytics.py backend/main.py backend/app/main.py backend/tests/test_admin_marketing_analytics.py
git commit -m "feat(marketing): [audos-P2] admin marketing funnel aggregation router, dual-registered"
```

---

## Task 11: Marketing analytics admin page

**Files:**
- Modify: `frontend/src/api/client.ts` (add `adminMarketingAnalyticsAPI`)
- Create: `frontend/src/pages/admin/AdminMarketingAnalyticsPage.tsx`
- Modify: `frontend/src/navigation/routes.ts` + `frontend/src/App.tsx`

**Interfaces:**
- Consumes: `adminMarketingAnalyticsAPI.funnel`, `MetricTimeSeriesChart` (`points:{date,aggregate,passes_threshold}[]`, `threshold`, `color`, `label`).

- [ ] **Step 1: Add the API wrapper** to `frontend/src/api/client.ts`:

```ts
export interface MarketingFunnel {
  period_days: number;
  events: { landing_page_view: number; landing_cta_click: number; lead_captured: number };
  rates: { cta_rate_pct: number; capture_rate_pct: number };
  daily: { date: string; landing_page_view: number; landing_cta_click: number; lead_captured: number }[];
}

export const adminMarketingAnalyticsAPI = {
  funnel: async (days = 30) =>
    api.get('/api/admin/marketing-analytics/funnel', { params: { days } }).then((r) => r.data as MarketingFunnel),
};
```

- [ ] **Step 2: Add the route** to `frontend/src/navigation/routes.ts`:

```ts
adminMarketingAnalytics: { path: '/admin/marketing-analytics', roles: ['ADMIN'] as RouteRole[] },
```

- [ ] **Step 3: Create the page** at `frontend/src/pages/admin/AdminMarketingAnalyticsPage.tsx` (reuse `MetricTimeSeriesChart`; map the daily series into its `{date, aggregate, passes_threshold}` point shape):

```tsx
import React, { useEffect, useState } from 'react';
import { Card } from '../../components/antigravity';
import { adminMarketingAnalyticsAPI, type MarketingFunnel } from '../../api/client';
import { AdminLayout } from './AdminLayout';
import { MetricTimeSeriesChart } from './MetricTimeSeriesChart';

const ACCENT = '#1f8e8b';

export const AdminMarketingAnalyticsPage: React.FC = () => {
  const [data, setData] = useState<MarketingFunnel | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    adminMarketingAnalyticsAPI
      .funnel(30)
      .then(setData)
      .catch((e) => setError(String(e?.message || 'Failed to load')));
  }, []);

  const points = (data?.daily || []).map((d) => ({
    date: d.date,
    aggregate: d.landing_cta_click,
    passes_threshold: true,
  }));

  return (
    <AdminLayout title="Marketing Analytics" subtitle="Pre-signup acquisition funnel (last 30 days)">
      {error && <Card><p className="text-[#b91c1c] text-sm">{error}</p></Card>}
      {data && (
        <>
          <div className="grid grid-cols-3 gap-4 mb-4">
            <Card><div className="text-xs text-[#6b7280]">Landing views</div>
              <div className="text-2xl font-semibold text-[#0b2b43]">{data.events.landing_page_view}</div></Card>
            <Card><div className="text-xs text-[#6b7280]">CTA clicks · {data.rates.cta_rate_pct}%</div>
              <div className="text-2xl font-semibold text-[#0b2b43]">{data.events.landing_cta_click}</div></Card>
            <Card><div className="text-xs text-[#6b7280]">Leads captured · {data.rates.capture_rate_pct}%</div>
              <div className="text-2xl font-semibold text-[#0b2b43]">{data.events.lead_captured}</div></Card>
          </div>
          <Card>
            <MetricTimeSeriesChart points={points} threshold={0} color={ACCENT} label="CTA clicks / day" />
          </Card>
        </>
      )}
    </AdminLayout>
  );
};
```

- [ ] **Step 4: Register the route in `frontend/src/App.tsx`** (lazy import + `<Route>` with `RequireAdminRoute`), same pattern as Task 6 Step 3.

- [ ] **Step 5: Type-check + build**

Run: `cd frontend && npx tsc --noEmit && npm run build`
Expected: both clean. (If `MetricTimeSeriesChart`'s `RagEvalPoint` import makes the point-shape mapping fail type-check, define a local `type FunnelPoint = { date: string; aggregate: number; passes_threshold: boolean }` and cast — do not modify the chart component.)

- [ ] **Step 6: Commit**

```bash
git add frontend/src/api/client.ts frontend/src/pages/admin/AdminMarketingAnalyticsPage.tsx frontend/src/navigation/routes.ts frontend/src/App.tsx
git commit -m "feat(marketing): [audos-P2] AdminMarketingAnalyticsPage + /admin/marketing-analytics route"
```

**→ Open PR 2 (`feat/marketing-analytics`). Run the P2 validation checklist before merge.**

---

# Per-PR Validation Checklists

**P1 (Lead CRM), before merge:**
1. `cd frontend && npx tsc --noEmit && npm run build` — clean.
2. `cd /Users/romainlecomte/Documents/GitHub/rolec && RELOPASS_QUERY_COUNTER_OFF=1 .venv311/bin/pytest backend/tests/test_admin_leads.py backend/tests/test_lead_capture.py -q` — all pass.
3. Route one-liner (`'lead'`) lists `/api/admin/leads*` and `/api/public/lead-capture` on `backend.main:app`.
4. Supabase `migration-drift` CI green; `get_advisors` (Supabase MCP) shows **0** RLS/anon findings on `leads` (the metric that matters most, per SEC-002 history).
5. Manual staging QA (Task 7 Step 3): demo submit → row in `/admin/leads` + correct match badge.
6. `package.json` diff empty.

**P2 (Marketing Analytics), before merge:**
1. `cd frontend && npx tsc --noEmit && npm run build` — clean.
2. `RELOPASS_QUERY_COUNTER_OFF=1 .venv311/bin/pytest backend/tests/test_public_track.py backend/tests/test_admin_marketing_analytics.py -q` — all pass.
3. Route one-liner (`'marketing'`, `'public/track'`) confirms both routes on `backend.main:app`.
4. **Event-name match check:** the strings in `FUNNEL_EVENTS` (`admin_marketing_analytics.py`) exactly equal the events emitted by `emitMarketingEvent`/`emit_event` (`landing_page_view`, `landing_cta_click`, `lead_captured`). A silent mismatch renders zeros without erroring.
5. Manual staging QA: load landing → click a CTA → `/admin/marketing-analytics` counts increment (view, click; capture increments after a demo submit).
6. `package.json` diff empty.

# Post-ship Success Metrics
- **GTM outcome:** P1 — leads triaged/week (target 100% within 5 business days), lead→qualified rate, lead→prospect-match rate. P2 — CTA click-through rate, capture rate, WoW funnel trend; once both live, lead→pipeline conversion.
- **Delivery/health (merge gates above):** `get_advisors` 0 findings on `leads`; routes live on `backend.main:app`; `package.json` unchanged; demo-form capture success ≥ current demo-submit success.

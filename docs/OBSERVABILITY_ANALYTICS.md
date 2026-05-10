# Observability Analytics

Workflow observability for user flows, recommendations, supplier engagement, and RFQ conversion.

## 1. Tracked Events

| Event | When | Location |
|-------|------|----------|
| `case_created` | Case finalized (POST /api/cases/{id}/create) | cases router |
| `services_selected` | Services upserted for assignment | main.py upsert_assignment_services |
| `services_answers_saved` | Service questionnaire answers saved | main.py upsert_service_answers |
| `recommendations_generated` | Batch or category recommendations returned | recommendations router |
| `supplier_viewed` | Admin views supplier detail (GET /api/suppliers/{id}) | suppliers router |
| `supplier_selected` | Vendor selected for RFQ (one per vendor) | main.py create_rfq |
| `rfq_created` | RFQ created with items and vendors | main.py create_rfq |
| `quote_received` | Vendor submits quote (POST /api/vendor/rfqs/{id}/quotes) | main.py submit_vendor_quote |
| `quote_compared` | Employee opens quotes with comparison=1 and 2+ quotes | main.py list_quotes_for_rfq |
| `quote_accepted` | Employee accepts quote (PATCH .../accept) | main.py accept_quote |

---

## 2. Files Changed

| Path | Change |
|------|--------|
| `backend/services/analytics_service.py` | **New** – emit_event(), event constants |
| `backend/database.py` | analytics_events table, insert_analytics_event, list_analytics_events, count_analytics_events_by_name |
| `backend/app/routers/cases.py` | Emit case_created on create |
| `backend/main.py` | Emit services_selected, services_answers_saved, rfq_created, supplier_selected |
| `backend/app/recommendations/router.py` | Emit recommendations_generated |
| `backend/app/routers/suppliers.py` | Emit supplier_viewed |
| `backend/app/routers/admin_workflow_analytics.py` | **New** – admin report endpoints |
| `supabase/migrations/20260326000000_analytics_events.sql` | **New** – Postgres schema |
| `docs/OBSERVABILITY_ANALYTICS.md` | **New** – this doc |

---

## 3. Logging / Instrumentation

- **Structured logs**: `log.info("analytics event=%s %s", event_name, json.dumps(...))`
- **Payload fields**: request_id, assignment_id, case_id, canonical_case_id, user_id, user_role, duration_ms, service_categories, counts, extra
- **Persistence**: analytics_events table (SQLite locally, Postgres via migration)
- **Non-blocking**: Persist failures are caught and logged; main request flow is not affected

---

## 4. Analytics / Report Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/admin/workflow/overview?days=30` | Aggregated metrics: event counts, supplier selection rate, RFQ conversion, quote response rate |
| `GET /api/admin/workflow/events?event_name=&days=7&limit=100` | Raw events for drill-down |

**Admin only** (Bearer token, admin role or @relopass.com allowlist).

---

## 5. Verification Steps

1. **Emit event**:
   ```bash
   python -c "
   from backend.services.analytics_service import emit_event, EVENT_CASE_CREATED
   emit_event(EVENT_CASE_CREATED, case_id='test-1')
   "
   ```

2. **Count events**:
   ```bash
   python -c "
   from backend.database import db
   print(db.count_analytics_events_by_name())
   "
   ```

3. **API**: Start backend, create case, select services, save answers, create RFQ; call `GET /api/admin/workflow/overview` with admin Bearer token.

4. **Postgres**: Run migration `20260326000000_analytics_events.sql`; verify table and RLS.

---

## 6. Deferred Items

- **quote_received, quote_compared, quote_accepted**: Instrument when quote create/accept/compare endpoints exist
- **supplier_viewed (employee/HR)**: Track when recommendations are viewed or supplier cards opened in UI (frontend instrumentation)
- **Frontend instrumentation**: Optional beacon for page views, CTA clicks
- **Dashboard UI**: Admin workflow analytics page in frontend

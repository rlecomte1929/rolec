from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .db import init_db
from .routers import (
    ab_tests,
    admin,
    admin_ai_unit_economics,
    admin_autopilot_metrics,
    admin_corrections,
    admin_dsar,
    admin_feature_flags,
    admin_exec_overview,
    coverage,
    admin_test_drive,
    admin_marketing_analytics,
    admin_rag_eval,
    admin_ocr_shadow,
    admin_work_items,
    admin_prompts,
    admin_leads,
    lead_capture,
    admin_source_change_review,
    advisors,
    ai_decisions,
    ai_feedback,
    payment,
    stripe_webhook,
    resources_activities,
    auth_page_config,
    assistant_router,
    policy_helpfulness,
    ocr,
    requirement_facts,
    admin_candidate_beam,
    admin_content_review,
    benefit_optimizer,
    case_forms_adhoc,
    cases,
    cases_admin,
    case_integrations,
    case_requirement_checklist,
    cases_read,
    cases_write,
    case_documents,
    conjoint,
    employee_quotes,
    employee_steps,
    provider_portal,
    supplier_rfq,
    provider_ratings,
    hr_vendor_performance,
    exception_requests,
    hr_analytics,
    hr_case_summary,
    hr_onboarding,
    hr_case_audit,
    hr_case_notes,
    coordinator,
    hr_case_detail,
    hr_intake_extraction,
    hr_roadmap_review,
    roadmap_regenerate,
    compliance,
    gdpr,
    privacy_consents,
    feedback,
    outcome_consent,
    outcomes_ingest,
    hr_case_resolve,
    hr_case_closure,
    hr_case_escalation,
    setup_assistant,
    hr_catalog,
    hr_company_invites,
    hr_vendor_widgets,
    research_requests,
    hr_coordination,
    employee_immigration_snapshot,
    employee_immigration_authority,
    immigration_documents,
    immigration_forms,
    immigration_gdpr,
    immigration_intake_consent,
    immigration_intake_interview,
    immigration_intake_profile,
    immigration_retrieve,
    immigration_status,
    marketplace,
    mobility_context,
    nlg,
    pets,
    policy_analysis,
    policy_canonical,
    policy_gaps,
    policy_publish,
    policy_summary,
    policy_templates,
    predictions,
    test_drive,
    rag_roadmap,
    relocation_profile,
    roadmap_audit,
    case_rule_updates,
    specialist_review,
    support,
    translation,
    admin_settings,
    admin_feedback,
    admin_admins,
    admin_audit_log,
    public_analytics,
    product_track,
    admin_product_metrics,
    public_corridor,
    geocoding,
    attestation,
)
from .recommendations.router import router as recommendations_router
from .recommendations.admin_debug import router as admin_recommendations_debug_router
from ..routes import relocation as relocation_routes
from ..routes import relocation_classify as relocation_classify_routes
from .seed import seed_demo_cases
from .services.pii_log_filter import install_pii_log_filter


def create_app() -> FastAPI:
    # [P5-9 H3] Central PII scrubber on the root logger — keeps the 5
    # audit patterns out of every record before any handler emits it.
    install_pii_log_filter()

    # [AIQ-1780] Vendor completers for the relopass LLM router. Registered here AND
    # in backend/main.py's lifespan — prod boots that app, this one backs the tests
    # and the modular cutover, and the registry is a process-global dict, so an
    # entry point that skips it silently reproduces the "zero extracted fields" bug.
    from .services.llm_router_clients import install_router_completers
    install_router_completers()

    init_db()
    seed_demo_cases()

    app = FastAPI(title="ReloPass Wizard API", version="1.0.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Pre-existing routers ──────────────────────────────────────────────────
    # [AUDIT-B9-cases-6] cases.router replaced by 3 modular routers (read/write/admin).
    # Original cases.py is retained as a support module for Pydantic models + private
    # helpers that cases_write.py still imports from. Its router is no longer wired.
    app.include_router(cases_read.router)
    app.include_router(case_requirement_checklist.router)
    app.include_router(case_integrations.router)  # I-4 — email plan + calendar .ics
    app.include_router(cases_write.router)
    app.include_router(case_documents.router)  # [DOCFLOW P1] case-scoped document upload/status
    app.include_router(cases_admin.router)
    app.include_router(case_forms_adhoc.router)  # [P4-3] ad-hoc "Add document"
    app.include_router(admin.router)
    app.include_router(admin_source_change_review.router)  # P2-02d material-change review queue
    app.include_router(ocr.router)  # [AIQ-1148] /api/ocr/process — general document OCR
    app.include_router(employee_quotes.router)
    app.include_router(provider_portal.router)  # H2 — external provider portal (/api/provider/{tasks,case-summary,profile})
    app.include_router(supplier_rfq.router)     # AIQ-1521 — supplier magic-link (/api/supplier/rfq)
    app.include_router(supplier_rfq.hr_router)  # AIQ-1521 — HR mints/sends the links
    app.include_router(provider_ratings.router)  # CATALOG-3 employee provider ratings
    app.include_router(hr_vendor_performance.router)  # NAV-SP-2 HR vendor performance dashboard
    app.include_router(employee_steps.router)  # [B11/AIQ-421] /api/employee/steps/4 → quote-request alias
    app.include_router(pets.router)
    app.include_router(support.router)
    app.include_router(translation.router)
    app.include_router(ab_tests.router)

    # ── Month-1 migration: Auth ───────────────────────────────────────────────
    # [AUDIT-C2.3] auth router moved from backend/main.py
    from .routers import auth  # noqa: PLC0415 — import kept local to avoid circular at module load
    app.include_router(auth.router)

    # ── Month-1 migration: HR cluster ─────────────────────────────────────────
    app.include_router(hr_catalog.router)
    app.include_router(hr_company_invites.router)
    app.include_router(hr_vendor_widgets.router)  # [B16/AIQ-422] bare-path vendor widget aliases
    app.include_router(research_requests.router)  # [AIQ-1349 P2] research-request intake
    app.include_router(hr_coordination.router)
    app.include_router(hr_analytics.router)
    app.include_router(hr_case_summary.router)  # AIQ-1697 — AI case summary proxy
    app.include_router(hr_onboarding.router)  # AIQ-1223c — deterministic onboarding inference
    # C1-11c-be: per-case detail reads consumed by the HR Dashboard surface.
    app.include_router(hr_case_detail.router)
    app.include_router(hr_roadmap_review.router)
    app.include_router(hr_intake_extraction.router)  # [W1-3] HR contract → proposed intake prefill
    app.include_router(roadmap_regenerate.router)  # [W1-2] recompute a case's milestones from the current generator
    app.include_router(hr_roadmap_review.metrics_router)  # [AIQ-1526] ops metrics for the HR notification
    # C1-16: GET /api/hr/cases/{id}/audit — chronological event timeline.
    app.include_router(hr_case_audit.router)
    # AIQ-1136 / NAV-HR-2-FU: GET/POST /api/hr/cases/{id}/notes — internal case notes.
    app.include_router(hr_case_notes.router)
    # AIQ-1414 Phase 3: POST /api/cases/{id}/coordinator/respond (flag-gated, dual-registered).
    app.include_router(coordinator.router)
    # P1-08c/d/e: roadmap as_of reconstruction + legal export + rule-change notifier.
    app.include_router(roadmap_audit.router)
    app.include_router(case_rule_updates.router)  # AIQ-693 — P2-02e rule-update banner read/dismiss
    # C1-12-be: resolve + escalate POST endpoints — closes the C1-12 deferral.
    app.include_router(hr_case_resolve.router)
    app.include_router(hr_case_escalation.router)  # W2-3 — HR case escalation
    app.include_router(hr_case_closure.router)  # [AIQ-2088] HR case closure
    app.include_router(setup_assistant.router)  # Setup & Help Assistant — read-only GET /api/hr/setup-status
    # [Parker-J] NLG exec-summary + policy TL;DR routes
    app.include_router(nlg.router)

    # ── Month-1 migration: Employee cluster ───────────────────────────────────
    app.include_router(immigration_intake_consent.router)
    app.include_router(immigration_intake_profile.router)
    app.include_router(immigration_intake_interview.router)
    app.include_router(immigration_status.router)
    app.include_router(immigration_gdpr.router)
    app.include_router(employee_immigration_snapshot.router)  # relocation-assistant Slice 2 — GET /api/employee/cases/{id}/immigration-snapshot
    app.include_router(employee_immigration_authority.router)  # IDR-260820-28EC — standing destination immigration-authority link
    app.include_router(gdpr.router)  # PRIV-001 / AIQ-469 — GDPR Art. 20 data-export
    app.include_router(privacy_consents.router)  # PRIV-005 / AIQ-473 — Art. 13 notice acknowledgement
    app.include_router(feedback.router)  # product "Share feedback" widget → public.feedback
    app.include_router(outcome_consent.router)  # P1-07c / AIQ-686 — outcome-sharing opt-in
    app.include_router(outcomes_ingest.router)  # P1-07d / AIQ-687 — internal outcome ingest trigger
    app.include_router(immigration_forms.router)  # IMM-11 — form library + PDF pre-fill
    app.include_router(immigration_documents.router)  # BL-OCR.2/AIQ-748 — POST /api/immigration/cases/{id}/documents
    app.include_router(immigration_retrieve.router)  # W1/AIQ-835 — POST /api/immigration/retrieve
    app.include_router(exception_requests.router)
    app.include_router(relocation_profile.router)
    app.include_router(marketplace.router)
    app.include_router(public_analytics.router)  # [audos-P2] public POST /api/public/track
    app.include_router(product_track.router)  # authenticated POST /api/track (product events → analytics_events)
    app.include_router(public_corridor.router)   # [audos] public GET /api/public/corridor-requirements
    # Counsel attestation. TWO routers, deliberately separate: admin_router is behind
    # require_admin, public_router is token-scoped with no auth. Keeping them distinct
    # makes the two-key boundary visible at registration, not just inside the handlers.
    app.include_router(attestation.admin_router)
    app.include_router(attestation.public_router)
    app.include_router(geocoding.router)   # [AIQ-1607] GET /api/employee/geocode/autocomplete
    app.include_router(advisors.router)
    app.include_router(ai_decisions.router)
    app.include_router(payment.router)  # Stripe roadmap paywall (TEST MODE) — POST /api/payment/checkout
    app.include_router(stripe_webhook.router)  # Stripe webhook Path A — POST /api/stripe/webhook
    # Auth Page Design — GET /api/public/auth-page-config (anon), PUT /api/admin/auth-page-config (admin)
    app.include_router(auth_page_config.router)
    app.include_router(assistant_router.router)  # policy-bridge domain routing — POST /api/assistant/route
    app.include_router(requirement_facts.router)  # [AIQ-1091] P4-02 requirement-facts extract
    app.include_router(admin_content_review.router)  # [AIQ-1821] content review queue
    app.include_router(admin_candidate_beam.router)  # corridor candidate beam review
    # [Parker-A] Case-duration prediction (canary: PREDICTIONS_ENABLED, default off)
    app.include_router(predictions.router)
    # [AIQ-1420] TD-2 test-drive self-serve provisioning (canary: RELOPASS_TEST_DRIVE_ENABLED, default off)
    app.include_router(test_drive.router)
    # [Parker-B] HR benefit-mix optimizer (Markowitz-style)
    app.include_router(benefit_optimizer.router)
    # [Parker-E] RLHF-lite human-feedback capture
    app.include_router(ai_feedback.router)
    # [AIQ-1581] city-level activity suggestions for the Resources page
    app.include_router(resources_activities.router)
    # [WS-E] end-user "was this answer helpful?" capture for policy answers
    app.include_router(policy_helpfulness.router)
    app.include_router(admin_ocr_shadow.router)
    # [Parker-G] AI unit-economics admin rollup
    app.include_router(admin_ai_unit_economics.router)
    app.include_router(admin_autopilot_metrics.router)  # Autopilot P4 — funnel + cost dashboard
    app.include_router(admin_rag_eval.router)
    app.include_router(admin_dsar.router)  # GDPR/DSAR desk — /api/admin/erasure-requests
    app.include_router(admin_feature_flags.router)  # Feature-flag console — /api/admin/feature-flags
    app.include_router(admin_exec_overview.router)  # Executive dashboard — GET /api/admin/exec-overview
    app.include_router(coverage.router)  # Admin coverage dashboard — GET /api/admin/coverage
    app.include_router(admin_test_drive.router)  # [AIQ-1428] TD-10 — GET /api/admin/test-drive/*
    app.include_router(admin_work_items.router)  # Mission Control P1 — demands console
    # [Parker-H] Conjoint (CBC) company-scoped HR/respondent API
    app.include_router(conjoint.router)
    app.include_router(admin_corrections.router)  # [AIQ-554] /api/admin/corrections/by-reason
    app.include_router(recommendations_router)
    app.include_router(admin_recommendations_debug_router, prefix="/api/admin")
    app.include_router(admin_prompts.router, prefix="/api/admin")
    app.include_router(admin_marketing_analytics.router, prefix="/api/admin")  # [audos-P2] pre-signup funnel
    app.include_router(admin_product_metrics.router, prefix="/api/admin")  # in-product event metrics (Feedback → Product metrics tab)
    app.include_router(admin_leads.router, prefix="/api/admin")  # [audos-P1] Lead CRM CRUD
    app.include_router(lead_capture.router)  # [audos-P1] public lead-capture — NO prefix (path baked into route)
    app.include_router(relocation_routes.router)
    app.include_router(relocation_routes.api_router)
    app.include_router(relocation_classify_routes.router)
    app.include_router(mobility_context.router)  # P2 circular-import fixed — safe to top-level import
    app.include_router(specialist_review.router)
    app.include_router(rag_roadmap.router)  # [P1-01d] /api/internal/rag/generate-roadmap
    app.include_router(compliance.router)  # [BL-Compliance.4] /api/compliance

    # ── AIQ-1219 PR2: policy analysis (PDF → workflow summary) ─────────────────
    app.include_router(policy_analysis.router)

    # ── Month-1 migration: HR Policy cluster ──────────────────────────────────
    app.include_router(policy_publish.router)
    # C2-06-FOLLOWUP: GET /api/hr/cases/{id}/policy-gaps — read-only gap surface.
    app.include_router(policy_gaps.router)
    app.include_router(policy_summary.router)
    app.include_router(policy_canonical.admin_router, prefix="/api/admin")
    app.include_router(policy_canonical.read_router, prefix="/api")
    app.include_router(policy_templates.router)
    app.include_router(admin_settings.router)  # [Task-4] admin AI-governance controls panel
    app.include_router(admin_feedback.router)  # [Task-6] unified feedback console
    app.include_router(admin_admins.router)  # [Task-7] admin lifecycle management
    app.include_router(admin_audit_log.router)  # [Task-7] platform audit-log viewer

    # [P4-4 / AIQ-1220] Cron HTTP triggers (inline CRON_SECRET auth). Mounted in
    # backend/main.py already; registered here too so the modular app + tests see
    # the /api/crons/* routes (e.g. the weekly hr-mobility-briefing endpoint).
    from .routers import crons  # noqa: PLC0415 — local import mirrors auth above
    app.include_router(crons.router)

    # Admin routers that were previously registered ONLY in backend/main.py (prod serves
    # them, but the modular app + app-mounted test harness returned 404 for them, and they
    # would 405 after the modular cutover). Mount them here too, mirroring the exact
    # prefixes used in backend/main.py. Local import mirrors the crons/auth pattern above
    # to avoid any module-load circular import.
    from .routers import (  # noqa: PLC0415
        admin_catalog,
        admin_mobility,
        admin_resources,
        admin_staging,
        admin_freshness,
        admin_review_queue,
        admin_notifications,
        admin_ops_analytics,
        admin_workflow_analytics,
        admin_collaboration,
        admin_prospects,
        admin_outreach,
        admin_form_templates,
    )
    from .routers.policy_config import admin_policy_config_router  # noqa: PLC0415

    app.include_router(admin_catalog.router)  # prefix baked into routes
    app.include_router(admin_mobility.router)  # prefix baked into routes
    app.include_router(admin_resources.router, prefix="/api/admin")
    app.include_router(admin_staging.router, prefix="/api/admin")
    app.include_router(admin_freshness.router, prefix="/api/admin")
    app.include_router(admin_freshness.crawl_router, prefix="/api/admin")
    app.include_router(admin_freshness.changes_router, prefix="/api/admin")
    app.include_router(admin_review_queue.router, prefix="/api/admin")
    app.include_router(admin_notifications.router, prefix="/api/admin")
    app.include_router(admin_ops_analytics.router, prefix="/api/admin")
    app.include_router(admin_workflow_analytics.router, prefix="/api/admin")
    app.include_router(admin_collaboration.router, prefix="/api/admin")
    app.include_router(admin_prospects.router, prefix="/api/admin")
    app.include_router(admin_outreach.router, prefix="/api/admin")
    app.include_router(admin_form_templates.router, prefix="/api/admin")
    app.include_router(admin_policy_config_router)

    from .routers import test_drive as test_drive_router  # TD-2 (AIQ-1420) test-drive provisioning
    app.include_router(test_drive_router.router)

    # ── Month-1 TODO: Tier 4 routers blocked on Month-0 P3 extraction ─────────
    # TODO [AUDIT-C2.3 / Month-0 P3]: add hr_policy_config + employee_policy_config
    # once those routers are extracted from the inline APIRouter objects in backend/main.py.

    return app


app = create_app()

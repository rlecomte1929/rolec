from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .db import init_db
from .routers import (
    ab_tests,
    admin,
    admin_ai_unit_economics,
    admin_corrections,
    admin_rag_eval,
    admin_ocr_shadow,
    admin_prompts,
    admin_source_change_review,
    advisors,
    ai_decisions,
    ai_feedback,
    ocr,
    benefit_optimizer,
    case_forms_adhoc,
    cases,
    cases_admin,
    case_integrations,
    cases_read,
    cases_write,
    case_documents,
    conjoint,
    employee_quotes,
    employee_steps,
    provider_ratings,
    hr_vendor_performance,
    exception_requests,
    hr_analytics,
    hr_onboarding,
    hr_export,
    hr_case_audit,
    hr_case_notes,
    hr_case_detail,
    compliance,
    gdpr,
    privacy_consents,
    hr_case_resolve,
    hr_case_escalation,
    hr_catalog,
    hr_vendor_widgets,
    hr_coordination,
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
    rag_roadmap,
    relocation_profile,
    roadmap_audit,
    specialist_review,
    support,
    translation,
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
    app.include_router(case_integrations.router)  # I-4 — email plan + calendar .ics
    app.include_router(cases_write.router)
    app.include_router(case_documents.router)  # [DOCFLOW P1] case-scoped document upload/status
    app.include_router(cases_admin.router)
    app.include_router(case_forms_adhoc.router)  # [P4-3] ad-hoc "Add document"
    app.include_router(admin.router)
    app.include_router(admin_source_change_review.router)  # P2-02d material-change review queue
    app.include_router(ocr.router)  # [AIQ-1148] /api/ocr/process — general document OCR
    app.include_router(employee_quotes.router)
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
    app.include_router(hr_vendor_widgets.router)  # [B16/AIQ-422] bare-path vendor widget aliases
    app.include_router(hr_coordination.router)
    app.include_router(hr_analytics.router)
    app.include_router(hr_onboarding.router)  # AIQ-1223c — deterministic onboarding inference
    app.include_router(hr_export.router)
    # C1-11c-be: per-case detail reads consumed by the HR Dashboard surface.
    app.include_router(hr_case_detail.router)
    # C1-16: GET /api/hr/cases/{id}/audit — chronological event timeline.
    app.include_router(hr_case_audit.router)
    # AIQ-1136 / NAV-HR-2-FU: GET/POST /api/hr/cases/{id}/notes — internal case notes.
    app.include_router(hr_case_notes.router)
    # P1-08c/d/e: roadmap as_of reconstruction + legal export + rule-change notifier.
    app.include_router(roadmap_audit.router)
    # C1-12-be: resolve + escalate POST endpoints — closes the C1-12 deferral.
    app.include_router(hr_case_resolve.router)
    app.include_router(hr_case_escalation.router)  # W2-3 — HR case escalation
    # [Parker-J] NLG exec-summary + policy TL;DR routes
    app.include_router(nlg.router)

    # ── Month-1 migration: Employee cluster ───────────────────────────────────
    app.include_router(immigration_intake_consent.router)
    app.include_router(immigration_intake_profile.router)
    app.include_router(immigration_intake_interview.router)
    app.include_router(immigration_status.router)
    app.include_router(immigration_gdpr.router)
    app.include_router(gdpr.router)  # PRIV-001 / AIQ-469 — GDPR Art. 20 data-export
    app.include_router(privacy_consents.router)  # PRIV-005 / AIQ-473 — Art. 13 notice acknowledgement
    app.include_router(immigration_forms.router)  # IMM-11 — form library + PDF pre-fill
    app.include_router(immigration_documents.router)  # BL-OCR.2/AIQ-748 — POST /api/immigration/cases/{id}/documents
    app.include_router(immigration_retrieve.router)  # W1/AIQ-835 — POST /api/immigration/retrieve
    app.include_router(exception_requests.router)
    app.include_router(relocation_profile.router)
    app.include_router(marketplace.router)
    app.include_router(advisors.router)
    app.include_router(ai_decisions.router)
    # [Parker-A] Case-duration prediction (canary: PREDICTIONS_ENABLED, default off)
    app.include_router(predictions.router)
    # [Parker-B] HR benefit-mix optimizer (Markowitz-style)
    app.include_router(benefit_optimizer.router)
    # [Parker-E] RLHF-lite human-feedback capture
    app.include_router(ai_feedback.router)
    app.include_router(admin_ocr_shadow.router)
    # [Parker-G] AI unit-economics admin rollup
    app.include_router(admin_ai_unit_economics.router)
    app.include_router(admin_rag_eval.router)
    # [Parker-H] Conjoint (CBC) company-scoped HR/respondent API
    app.include_router(conjoint.router)
    app.include_router(admin_corrections.router)  # [AIQ-554] /api/admin/corrections/by-reason
    app.include_router(recommendations_router)
    app.include_router(admin_recommendations_debug_router, prefix="/api/admin")
    app.include_router(admin_prompts.router, prefix="/api/admin")
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

    # [P4-4 / AIQ-1220] Cron HTTP triggers (inline CRON_SECRET auth). Mounted in
    # backend/main.py already; registered here too so the modular app + tests see
    # the /api/crons/* routes (e.g. the weekly hr-mobility-briefing endpoint).
    from .routers import crons  # noqa: PLC0415 — local import mirrors auth above
    app.include_router(crons.router)

    # ── Month-1 TODO: Tier 4 routers blocked on Month-0 P3 extraction ─────────
    # TODO [AUDIT-C2.3 / Month-0 P3]: add hr_policy_config + employee_policy_config
    # once those routers are extracted from the inline APIRouter objects in backend/main.py.

    return app


app = create_app()

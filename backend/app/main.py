from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .db import init_db
from .routers import (
    ab_tests,
    admin,
    advisors,
    cases,
    employee_quotes,
    exception_requests,
    hr_analytics,
    hr_catalog,
    hr_coordination,
    immigration,
    marketplace,
    mobility_context,
    pets,
    policy_canonical,
    policy_feedback,
    policy_publish,
    policy_summary,
    policy_templates,
    relocation_profile,
    support,
)
from .recommendations.router import router as recommendations_router
from .recommendations.admin_debug import router as admin_recommendations_debug_router
from ..routes import relocation as relocation_routes
from ..routes import relocation_classify as relocation_classify_routes
from .seed import seed_demo_cases
<<<<<<< feat/migration-month1
# TODO [AUDIT-A9.3]: change to `.services.pii_log_filter` once A9.3 lands on this branch
from ..services.pii_log_filter import install_pii_log_filter  # noqa: E402
=======
from .services.pii_log_filter import install_pii_log_filter
>>>>>>> main


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
    app.include_router(cases.router)
    app.include_router(admin.router)
    app.include_router(employee_quotes.router)
    app.include_router(pets.router)
    app.include_router(support.router)
    app.include_router(ab_tests.router)

    # ── Month-1 migration: Auth ───────────────────────────────────────────────
    # [AUDIT-C2.3] auth router moved from backend/main.py
    from .routers import auth  # noqa: PLC0415 — import kept local to avoid circular at module load
    app.include_router(auth.router)

    # ── Month-1 migration: HR cluster ─────────────────────────────────────────
    app.include_router(hr_catalog.router)
    app.include_router(hr_coordination.router)
    app.include_router(hr_analytics.router)

    # ── Month-1 migration: Employee cluster ───────────────────────────────────
    app.include_router(immigration.router)
    app.include_router(exception_requests.router)
    app.include_router(relocation_profile.router)
    app.include_router(marketplace.router)
    app.include_router(advisors.router)
    app.include_router(recommendations_router)
    app.include_router(admin_recommendations_debug_router, prefix="/api/admin")
    app.include_router(relocation_routes.router)
    app.include_router(relocation_routes.api_router)
    app.include_router(relocation_classify_routes.router)
    app.include_router(mobility_context.router)  # P2 circular-import fixed — safe to top-level import

    # ── Month-1 migration: HR Policy cluster ──────────────────────────────────
    app.include_router(policy_publish.router)
    app.include_router(policy_summary.router)
    app.include_router(policy_feedback.router)
    app.include_router(policy_canonical.admin_router, prefix="/api/admin")
    app.include_router(policy_canonical.read_router, prefix="/api")
    app.include_router(policy_templates.router)

    # ── Month-1 TODO: Tier 4 routers blocked on Month-0 P3 extraction ─────────
    # TODO [AUDIT-C2.3 / Month-0 P3]: add hr_policy_config + employee_policy_config
    # once those routers are extracted from the inline APIRouter objects in backend/main.py.

    return app


app = create_app()

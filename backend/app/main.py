from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .db import init_db
from .routers import cases, admin, employee_quotes, pets, support, ab_tests
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

    app.include_router(cases.router)
    app.include_router(admin.router)
    app.include_router(employee_quotes.router)
    app.include_router(pets.router)
    app.include_router(support.router)
    app.include_router(ab_tests.router)
    return app


app = create_app()

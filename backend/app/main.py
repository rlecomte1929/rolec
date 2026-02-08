from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .db import init_db
from .routers import cases, admin
from .seed import seed_demo_cases


def create_app() -> FastAPI:
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
    return app


app = create_app()

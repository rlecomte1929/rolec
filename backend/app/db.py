import logging

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from ..db_config import DATABASE_URL

log = logging.getLogger(__name__)

_connect_args: dict = {}
if DATABASE_URL.startswith("sqlite"):
    _connect_args = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, connect_args=_connect_args)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def init_db() -> None:
    from . import models  # noqa: F401 – registers tables with Base
    Base.metadata.create_all(bind=engine)
    log.info("DB schema ensured (SQLAlchemy tables) — %s", DATABASE_URL.split("@")[-1] if "@" in DATABASE_URL else DATABASE_URL)

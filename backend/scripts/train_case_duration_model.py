"""Train and persist the Cox case-duration model (Parker-A).

Usage:
    python -m backend.scripts.train_case_duration_model

Builds the survival frame from live case/milestone/assignment data, fits the Cox
model (or an unsafe-to-serve sentinel when there is too little signal), writes a
pickled blob row into public.ml_models, and emits a structured log line. Runs as
the configured DB principal — in production that is the Supabase service_role,
which is the only writer permitted by the ml_models RLS policy.

This is the *only* place the model is trained. The request path never trains.
"""
from __future__ import annotations

import logging
import sys

from backend.app.db import SessionLocal
from backend.app.services.case_duration_model import (
    InsufficientDataError,
    MODEL_KEY,
    build_survival_frame,
    persist_model,
    train_case_duration_model,
)

log = logging.getLogger("relopass.ml.case_duration")


def main() -> int:
    logging.basicConfig(level=logging.INFO)
    with SessionLocal() as session:
        df = build_survival_frame(session)
        log.info(
            "case_duration: built survival frame",
            extra={"event": "case_duration.frame_built", "n_rows": int(len(df))},
        )
        try:
            model = train_case_duration_model(df)
        except InsufficientDataError as exc:
            log.warning(
                "case_duration: training refused — insufficient data",
                extra={"event": "case_duration.train_refused", "reason": str(exc)},
            )
            print(f"Training refused: {exc}", file=sys.stderr)
            return 1

        persist_model(session, model)
        log.info(
            "case_duration: model persisted to ml_models",
            extra={
                "event": "case_duration.persisted",
                "model_key": MODEL_KEY,
                "model_version": model.model_version,
                "status": model.status,
                "concordance": model.concordance,
                "n_training_rows": model.n_training_rows,
            },
        )
        print(
            f"Persisted model_key={MODEL_KEY} version={model.model_version} "
            f"status={model.status} concordance={model.concordance} "
            f"n_rows={model.n_training_rows}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

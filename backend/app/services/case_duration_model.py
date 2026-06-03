"""Cox proportional-hazards survival model for relocation case duration.

Parker-framework step A — the first quantitative prediction in ReloPass. Given a
case, estimate how many days remain until it closes, with an 80% interval.

Heavy numeric imports (pandas, numpy, lifelines, scikit-learn) are deferred to the
inside of functions on purpose: importing this module — and therefore importing the
predictions router and booting the FastAPI app — must never fail on a machine that
has not installed the ML extras from requirements.txt. Only code paths that actually
fit/predict require those libraries to be present.
"""
from __future__ import annotations

import logging
import pickle
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

if TYPE_CHECKING:  # import only for type checkers, never at runtime
    import pandas as pd
    from lifelines import CoxPHFitter

# Structured logger. Reuses the project logging stack (python-json-logger +
# the central PII scrubber installed in app.main) rather than standing up a new
# observability sink — matches ai_trace_logger's `logging.getLogger(__name__)`.
log = logging.getLogger("relopass.ml.case_duration")

MODEL_KEY = "case_duration_cox"
MODEL_VERSION = "1.0.0"

MIN_TRAINING_ROWS = 50
UNSAFE_CONCORDANCE = 0.55
L2_PENALIZER = 0.1

REQUIRED_COLUMNS: List[str] = ["duration_days", "event_observed"]
CATEGORICAL_COVARIATES: List[str] = [
    "destination_country",
    "origin_country",
    "band",
    "seasonality_quarter",
]
NUMERIC_COVARIATES: List[str] = ["dependents_count", "service_count"]
COVARIATE_COLUMNS: List[str] = CATEGORICAL_COVARIATES + NUMERIC_COVARIATES


class InsufficientDataError(ValueError):
    """Raised when a survival frame is too small or missing required columns.

    Distinct from the *all-censored* case (zero observed events): that is not an
    error — `train_case_duration_model` returns an unsafe-to-serve sentinel model
    so the caller can fall back to a deterministic estimate.
    """


class CaseDurationModel:
    """Serialisable wrapper around a fitted Cox model plus deterministic fallbacks.

    Pickled whole into `ml_models.pickled_blob`. Carries everything the request
    path needs so it never has to rebuild the training frame: the fitter, the
    exact one-hot design columns, and per-destination mean-duration priors used
    when the model is unsafe to serve or a covariate level is unseen.
    """

    def __init__(
        self,
        *,
        fitter: "Optional[CoxPHFitter]",
        feature_columns: List[str],
        model_version: str,
        n_training_rows: int,
        concordance: Optional[float],
        status: str,
        fallback_by_country: Dict[str, float],
        overall_mean_duration: float,
    ) -> None:
        self.fitter = fitter
        self.feature_columns = feature_columns
        self.model_version = model_version
        self.n_training_rows = n_training_rows
        self.concordance = concordance
        self.status = status  # 'active' | 'unsafe_to_serve'
        self.fallback_by_country = fallback_by_country
        self.overall_mean_duration = overall_mean_duration

    @property
    def is_servable(self) -> bool:
        return self.status == "active" and self.fitter is not None


# ──────────────────────────────────────────────────────────────────────────────
# Dataset construction
# ──────────────────────────────────────────────────────────────────────────────

_TERMINAL_CASE_STATUSES = {"completed", "closed", "done", "archived"}


def build_survival_frame(session: Any) -> "pd.DataFrame":
    """Join wizard_cases + case_milestones + case_assignments into a survival frame.

    Columns returned: case_id, duration_days, event_observed (1 = case closed /
    right-censored = 0), and the covariates in COVARIATE_COLUMNS.

    Event/duration semantics (no explicit terminal timestamp exists on
    wizard_cases): a case counts as an *observed event* when its status is
    terminal or every one of its milestones is `done`; duration is then the span
    from creation to the last milestone actual_date (falling back to updated_at).
    Otherwise the case is right-censored at its last observed activity.
    """
    import json

    import pandas as pd
    from sqlalchemy import text as sql_text

    rows = session.execute(
        sql_text(
            """
            SELECT c.id            AS case_id,
                   c.created_at    AS created_at,
                   c.updated_at    AS updated_at,
                   c.status        AS status,
                   c.dest_country  AS destination_country,
                   c.origin_country AS origin_country,
                   c.draft_json    AS draft_json,
                   m.total_ms      AS total_ms,
                   m.done_ms       AS done_ms,
                   m.last_actual   AS last_actual
            FROM public.wizard_cases c
            LEFT JOIN (
                SELECT case_id,
                       COUNT(*)                              AS total_ms,
                       COUNT(*) FILTER (WHERE status = 'done') AS done_ms,
                       MAX(actual_date)                      AS last_actual
                FROM public.case_milestones
                GROUP BY case_id
            ) m ON m.case_id = c.id
            """
        )
    ).mappings().all()

    records: List[Dict[str, Any]] = []
    now = datetime.now(timezone.utc)
    for r in rows:
        created = _as_datetime(r.get("created_at"))
        if created is None:
            continue
        total_ms = int(r.get("total_ms") or 0)
        done_ms = int(r.get("done_ms") or 0)
        status = (r.get("status") or "").lower()
        is_event = status in _TERMINAL_CASE_STATUSES or (total_ms > 0 and done_ms == total_ms)

        end = _as_datetime(r.get("last_actual")) or _as_datetime(r.get("updated_at")) or now
        duration_days = max((end - created).days, 0)

        draft = _safe_json(r.get("draft_json"))
        records.append(
            {
                "case_id": r.get("case_id"),
                "duration_days": duration_days,
                "event_observed": 1 if is_event else 0,
                "destination_country": (r.get("destination_country") or "UNK"),
                "origin_country": (r.get("origin_country") or "UNK"),
                "band": _extract_band(draft),
                "dependents_count": _extract_dependents(draft),
                "service_count": _extract_service_count(draft),
                "seasonality_quarter": f"Q{((created.month - 1) // 3) + 1}",
            }
        )

    return pd.DataFrame.from_records(records, columns=["case_id"] + REQUIRED_COLUMNS + COVARIATE_COLUMNS)


def build_case_covariates(session: Any, case_id: str) -> Optional[Dict[str, Any]]:
    """Build the single covariate row for one case, for request-time prediction.

    Returns None when the case does not exist. `elapsed_days` is included so the
    caller can convert a predicted *total* duration into a *remaining* one.
    """
    from sqlalchemy import text as sql_text

    row = session.execute(
        sql_text(
            """
            SELECT id, created_at, dest_country, origin_country, draft_json
            FROM public.wizard_cases WHERE id = :cid
            """
        ),
        {"cid": case_id},
    ).mappings().first()
    if not row:
        return None

    created = _as_datetime(row.get("created_at")) or datetime.now(timezone.utc)
    draft = _safe_json(row.get("draft_json"))
    elapsed = max((datetime.now(timezone.utc) - created).days, 0)
    return {
        "destination_country": (row.get("dest_country") or "UNK"),
        "origin_country": (row.get("origin_country") or "UNK"),
        "band": _extract_band(draft),
        "dependents_count": _extract_dependents(draft),
        "service_count": _extract_service_count(draft),
        "seasonality_quarter": f"Q{((created.month - 1) // 3) + 1}",
        "elapsed_days": elapsed,
        "destination_country_value": (row.get("dest_country") or "UNK"),
    }


# ──────────────────────────────────────────────────────────────────────────────
# Model fitting
# ──────────────────────────────────────────────────────────────────────────────


def _validate_frame(df: "pd.DataFrame") -> None:
    missing = [c for c in REQUIRED_COLUMNS + COVARIATE_COLUMNS if c not in df.columns]
    if missing:
        raise InsufficientDataError(f"survival frame missing columns: {missing}")
    if len(df) < MIN_TRAINING_ROWS:
        log.warning(
            "case_duration: refusing to fit — too few rows",
            extra={"event": "case_duration.insufficient_rows", "n_rows": len(df), "min_rows": MIN_TRAINING_ROWS},
        )
        raise InsufficientDataError(
            f"need >= {MIN_TRAINING_ROWS} training rows, got {len(df)}"
        )


def _design_matrix(
    df: "pd.DataFrame", feature_columns: Optional[List[str]] = None
) -> "Tuple[pd.DataFrame, List[str]]":
    """One-hot encode categoricals + keep numerics. Returns (design, feature_columns).

    The design frame always carries duration_days + event_observed so it can be
    handed straight to lifelines. When `feature_columns` is supplied the encoded
    frame is reindexed onto it (unseen levels → all-zero columns), which keeps
    train/predict and per-fold encodings perfectly aligned.
    """
    import pandas as pd

    cats = pd.get_dummies(
        df[CATEGORICAL_COVARIATES].astype("string").fillna("UNK"),
        columns=CATEGORICAL_COVARIATES,
        prefix=CATEGORICAL_COVARIATES,
        drop_first=False,
        dtype=float,
    )
    nums = df[NUMERIC_COVARIATES].apply(pd.to_numeric, errors="coerce").fillna(0.0).astype(float)
    features = pd.concat([cats, nums], axis=1)

    if feature_columns is None:
        feature_columns = list(features.columns)
    else:
        features = features.reindex(columns=feature_columns, fill_value=0.0)

    design = features.copy()
    design["duration_days"] = pd.to_numeric(df["duration_days"], errors="coerce").fillna(0.0).clip(lower=0.0)
    design["event_observed"] = pd.to_numeric(df["event_observed"], errors="coerce").fillna(0).astype(int)
    return design, feature_columns


def _fit(df: "pd.DataFrame", feature_columns: Optional[List[str]] = None) -> "Tuple[CoxPHFitter, List[str]]":
    from lifelines import CoxPHFitter

    design, feature_columns = _design_matrix(df, feature_columns)
    fitter = CoxPHFitter(penalizer=L2_PENALIZER)
    fitter.fit(design, duration_col="duration_days", event_col="event_observed", show_progress=False)
    return fitter, feature_columns


def fit_cox_model(df: "pd.DataFrame") -> "CoxPHFitter":
    """Fit a Cox PH model with L2 penalizer 0.1. Returns the lifelines CoxPHFitter.

    Raises InsufficientDataError when the frame is missing required columns, has
    fewer than MIN_TRAINING_ROWS rows, or contains zero observed events (a Cox
    model is undefined without at least one event).
    """
    _validate_frame(df)
    import pandas as pd

    n_events = int(pd.to_numeric(df["event_observed"], errors="coerce").fillna(0).sum())
    if n_events < 1:
        raise InsufficientDataError("cannot fit a Cox model with zero observed events")
    fitter, _ = _fit(df)
    return fitter


def cross_validated_concordance(df: "pd.DataFrame", k: int = 5) -> float:
    """k-fold cross-validated Harrell's C-index. Folds with no test events are skipped."""
    _validate_frame(df)
    import numpy as np
    from sklearn.model_selection import KFold

    _, feature_columns = _design_matrix(df)  # global column set, stable across folds
    df = df.reset_index(drop=True)

    splitter = KFold(n_splits=k, shuffle=True, random_state=42)
    scores: List[float] = []
    for train_idx, test_idx in splitter.split(df):
        train_df = df.iloc[train_idx]
        test_df = df.iloc[test_idx]
        if int(train_df["event_observed"].sum()) < 1 or int(test_df["event_observed"].sum()) < 1:
            continue
        try:
            fitter, _ = _fit(train_df, feature_columns)
            test_design, _ = _design_matrix(test_df, feature_columns)
            scores.append(float(fitter.score(test_design, scoring_method="concordance_index")))
        except Exception as exc:  # a degenerate fold should not sink the whole CV
            log.warning(
                "case_duration: CV fold failed",
                extra={"event": "case_duration.cv_fold_failed", "error": str(exc)},
            )
            continue

    if not scores:
        return 0.0
    return float(np.mean(scores))


def train_case_duration_model(df: "pd.DataFrame") -> CaseDurationModel:
    """Full training orchestration → a servable (or sentinel) CaseDurationModel.

    - Missing columns / too few rows → InsufficientDataError.
    - Zero observed events (all right-censored) → unsafe-to-serve sentinel (no
      crash), so the request path falls back to per-country mean duration.
    - Concordance < UNSAFE_CONCORDANCE → unsafe-to-serve (kept, but the route
      serves the deterministic fallback instead of the model).
    """
    _validate_frame(df)
    import pandas as pd

    fallback_by_country, overall_mean = _fallback_priors(df)
    n_rows = int(len(df))
    n_events = int(pd.to_numeric(df["event_observed"], errors="coerce").fillna(0).sum())

    if n_events < 1:
        log.warning(
            "case_duration: all cases right-censored — emitting unsafe sentinel",
            extra={"event": "case_duration.all_censored", "n_rows": n_rows},
        )
        return CaseDurationModel(
            fitter=None,
            feature_columns=[],
            model_version=MODEL_VERSION,
            n_training_rows=n_rows,
            concordance=None,
            status="unsafe_to_serve",
            fallback_by_country=fallback_by_country,
            overall_mean_duration=overall_mean,
        )

    concordance = cross_validated_concordance(df, k=5)
    fitter, feature_columns = _fit(df)
    status = "active" if concordance >= UNSAFE_CONCORDANCE else "unsafe_to_serve"
    log.info(
        "case_duration: model trained",
        extra={
            "event": "case_duration.trained",
            "model_key": MODEL_KEY,
            "model_version": MODEL_VERSION,
            "n_training_rows": n_rows,
            "concordance": round(concordance, 4),
            "status": status,
        },
    )
    return CaseDurationModel(
        fitter=fitter,
        feature_columns=feature_columns,
        model_version=MODEL_VERSION,
        n_training_rows=n_rows,
        concordance=concordance,
        status=status,
        fallback_by_country=fallback_by_country,
        overall_mean_duration=overall_mean,
    )


def _fallback_priors(df: "pd.DataFrame") -> "Tuple[Dict[str, float], float]":
    import pandas as pd

    dur = pd.to_numeric(df["duration_days"], errors="coerce").fillna(0.0)
    overall = float(dur.mean()) if len(dur) else 0.0
    by_country = (
        df.assign(_d=dur)
        .groupby("destination_country")["_d"]
        .mean()
        .astype(float)
        .to_dict()
    )
    return by_country, overall


# ──────────────────────────────────────────────────────────────────────────────
# Prediction
# ──────────────────────────────────────────────────────────────────────────────


def predict_remaining_duration(
    model: CaseDurationModel, case_id: str, session: Any
) -> Dict[str, Any]:
    """Predict remaining days to close for a case.

    Returns {median_days, p20_days, p80_days, model_version, n_training_cases}.
    When the model is unsafe to serve (or the destination is unseen) a
    deterministic per-destination mean-duration estimate is returned instead.
    """
    import pandas as pd

    covs = build_case_covariates(session, case_id)
    if covs is None:
        raise InsufficientDataError(f"case not found: {case_id}")

    elapsed = int(covs.get("elapsed_days") or 0)
    dest = covs.get("destination_country_value") or covs.get("destination_country") or "UNK"

    if not model.is_servable:
        total = model.fallback_by_country.get(dest, model.overall_mean_duration)
        return _remaining_dict(total * 0.7, total, total * 1.3, elapsed, model)

    row = {k: covs.get(k) for k in COVARIATE_COLUMNS}
    design, _ = _design_matrix(pd.DataFrame([{**row, "duration_days": 0, "event_observed": 0}]), model.feature_columns)
    X = design[model.feature_columns]

    median = _percentile_or_nan(model, X, 0.5)
    p20 = _percentile_or_nan(model, X, 0.8)  # 20th pct of duration = 80% still surviving
    p80 = _percentile_or_nan(model, X, 0.2)  # 80th pct of duration = 20% still surviving

    if any(_is_bad(v) for v in (median, p20, p80)):
        total = model.fallback_by_country.get(dest, model.overall_mean_duration)
        return _remaining_dict(total * 0.7, total, total * 1.3, elapsed, model)

    return _remaining_dict(p20, median, p80, elapsed, model)


def _percentile_or_nan(model: CaseDurationModel, X: "pd.DataFrame", p: float) -> float:
    try:
        val = model.fitter.predict_percentile(X, p=p)
        return float(val.iloc[0]) if hasattr(val, "iloc") else float(val)
    except Exception:
        return float("nan")


def _remaining_dict(
    p20_total: float, median_total: float, p80_total: float, elapsed: int, model: CaseDurationModel
) -> Dict[str, Any]:
    return {
        "median_days": _to_remaining(median_total, elapsed),
        "p20_days": _to_remaining(p20_total, elapsed),
        "p80_days": _to_remaining(p80_total, elapsed),
        "model_version": model.model_version,
        "n_training_cases": int(model.n_training_rows),
    }


def _to_remaining(total_days: float, elapsed: int) -> int:
    if _is_bad(total_days):
        return 0
    return int(max(round(total_days) - elapsed, 0))


# ──────────────────────────────────────────────────────────────────────────────
# Persistence (ml_models table)
# ──────────────────────────────────────────────────────────────────────────────


# SECURITY — trusted-only pickle boundary: the CaseDurationModel blob is produced
# exclusively by this backend (the CLI trainer running as the Supabase service
# role) and stored in public.ml_models, which has RLS enabled, anon REVOKEd, and
# only admin SELECT. No user-supplied bytes ever reach pickle.loads below. If that
# write path ever opens up, replace pickle with a schema-validated serializer.
def persist_model(session: Any, model: CaseDurationModel) -> None:
    """Insert a pickled CaseDurationModel into public.ml_models (service-role write)."""
    import json

    from sqlalchemy import text as sql_text

    blob = pickle.dumps(model, protocol=pickle.HIGHEST_PROTOCOL)
    session.execute(
        sql_text(
            """
            INSERT INTO public.ml_models
                (model_key, version, pickled_blob, n_training_rows, concordance, status, metadata)
            VALUES
                (:model_key, :version, :blob, :n_rows, :concordance, :status, CAST(:metadata AS jsonb))
            """
        ),
        {
            "model_key": MODEL_KEY,
            "version": model.model_version,
            "blob": blob,
            "n_rows": model.n_training_rows,
            "concordance": model.concordance,
            "status": model.status,
            "metadata": json.dumps(
                {
                    "feature_columns": model.feature_columns,
                    "overall_mean_duration": model.overall_mean_duration,
                }
            ),
        },
    )
    session.commit()


def load_active_model(session: Any, model_key: str = MODEL_KEY) -> Optional[CaseDurationModel]:
    """Load the most recently trained model for `model_key`, or None if absent."""
    from sqlalchemy import text as sql_text

    row = session.execute(
        sql_text(
            """
            SELECT pickled_blob FROM public.ml_models
            WHERE model_key = :model_key
            ORDER BY trained_at DESC
            LIMIT 1
            """
        ),
        {"model_key": model_key},
    ).mappings().first()
    if not row or row.get("pickled_blob") is None:
        return None
    try:
        blob = row["pickled_blob"]
        if isinstance(blob, memoryview):
            blob = blob.tobytes()
        return pickle.loads(bytes(blob))
    except Exception as exc:
        log.warning(
            "case_duration: failed to unpickle stored model",
            extra={"event": "case_duration.unpickle_failed", "error": str(exc)},
        )
        return None


# ──────────────────────────────────────────────────────────────────────────────
# Small helpers (stdlib only — safe at import time)
# ──────────────────────────────────────────────────────────────────────────────


def _is_bad(v: Any) -> bool:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return True
    return f != f or f in (float("inf"), float("-inf"))  # NaN or inf


def _as_datetime(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


def _safe_json(value: Any) -> Dict[str, Any]:
    import json

    if not value:
        return {}
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else {}
    except (ValueError, TypeError):
        return {}


def _extract_band(draft: Dict[str, Any]) -> str:
    for path in (("employee", "band"), ("employee", "seniority"), ("band",), ("seniority",)):
        cur: Any = draft
        for key in path:
            cur = cur.get(key) if isinstance(cur, dict) else None
            if cur is None:
                break
        if isinstance(cur, str) and cur.strip():
            return cur.strip()
    return "UNK"


def _extract_dependents(draft: Dict[str, Any]) -> int:
    family = draft.get("family") if isinstance(draft.get("family"), dict) else {}
    for container in (family, draft):
        if not isinstance(container, dict):
            continue
        for key in ("dependents_count", "dependentsCount", "dependents"):
            val = container.get(key)
            if isinstance(val, (int, float)):
                return int(val)
            if isinstance(val, list):
                return len(val)
    return 0


def _extract_service_count(draft: Dict[str, Any]) -> int:
    for key in ("selected_services", "selectedServices", "services"):
        val = draft.get(key)
        if isinstance(val, list):
            return len(val)
        if isinstance(val, dict):
            return len(val)
    return 0

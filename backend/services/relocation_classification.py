from typing import Any, Dict, List, Optional

from .relocation_profile import compute_missing_fields
from .relocation_classifier import classify_case


def compute_case_classification(profile: Dict[str, Any]) -> Dict[str, Any]:
    normalized = profile or {}
    missing_fields = normalized.get("missing_fields")
    if not isinstance(missing_fields, list):
        missing_fields = compute_missing_fields(normalized)

    classification = classify_case(normalized, missing_fields)
    payload = classification.model_dump()
    payload["metadata"] = {"engine": "deterministic_v1"}
    return payload


def persist_case_classification(
    db_session,
    case_id: str,
    input_payload: Dict[str, Any],
    output_payload: Dict[str, Any],
    model_provider: Optional[str] = None,
    model_name: Optional[str] = None,
    error: Optional[str] = None,
) -> None:
    version = _next_artifact_version(db_session, case_id)

    artifact_payload = {
        "case_id": case_id,
        "artifact_type": "case_classification",
        "version": version,
        "content": output_payload,
        "content_text": None,
    }
    artifact_res = db_session.table("relocation_artifacts").insert(artifact_payload).execute()
    if artifact_res.error:
        message = getattr(artifact_res.error, "message", str(artifact_res.error))
        raise RuntimeError(message)

    run_payload = {
        "case_id": case_id,
        "run_type": "case_classification",
        "input_payload": input_payload,
        "output_payload": output_payload,
        "model_provider": model_provider,
        "model_name": model_name,
        "error": error,
    }
    run_res = db_session.table("relocation_runs").insert(run_payload).execute()
    if run_res.error:
        message = getattr(run_res.error, "message", str(run_res.error))
        raise RuntimeError(message)


def _next_artifact_version(db_session, case_id: str) -> int:
    result = (
        db_session.table("relocation_artifacts")
        .select("version")
        .eq("case_id", case_id)
        .eq("artifact_type", "case_classification")
        .order("version", desc=True)
        .limit(1)
        .execute()
    )
    if result.error:
        message = getattr(result.error, "message", str(result.error))
        raise RuntimeError(message)
    if result.data:
        return int(result.data[0]["version"]) + 1
    return 1

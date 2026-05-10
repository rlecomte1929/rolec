"""
Storage path helpers for policy documents (shared by API and import pipeline).
"""
from __future__ import annotations

BUCKET_HR_POLICIES = "hr-policies"


def resolve_policy_storage_object_key(raw: str) -> str:
    """
    Resolve raw file_url / storage_path to object key for storage.from_(BUCKET_HR_POLICIES).
    """
    if not raw or not isinstance(raw, str):
        return ""
    s = raw.strip()
    if not s:
        return ""
    if s.startswith("http://") or s.startswith("https://"):
        try:
            from urllib.parse import urlparse

            parsed = urlparse(s)
            path = parsed.path or ""
            if "/hr-policies/" in path:
                return path.split("/hr-policies/", 1)[-1].lstrip("/")
            return ""
        except Exception:
            return ""
    if s.startswith("hr-policies/"):
        return s[len("hr-policies/") :]
    if "/hr-policies/" in s:
        return s.split("/hr-policies/", 1)[-1]
    if s.startswith("companies/"):
        return s
    return ""


def normalize_policy_storage_object_key(path: str) -> str:
    return resolve_policy_storage_object_key(path)

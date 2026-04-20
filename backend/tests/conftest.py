"""Pytest hooks for backend tests."""
from __future__ import annotations

import os

import pytest


def pytest_runtest_setup(item: pytest.Item) -> None:
    if "policy_assistant_audit" not in item.keywords:
        return
    if os.environ.get("RUN_POLICY_ASSISTANT_AUDIT") == "1":
        return
    markexpr = getattr(item.config.option, "markexpr", "") or ""
    if "policy_assistant_audit" in markexpr:
        return
    pytest.skip(
        "Policy assistant audit tests are opt-in: use "
        "`pytest -m policy_assistant_audit` or set RUN_POLICY_ASSISTANT_AUDIT=1"
    )

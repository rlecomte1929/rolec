"""Cold-start warm-up (_warmup_cold_paths) must touch the cold resources and be fully best-effort.

Imports the prod app (backend.main) — needs RELOPASS_QUERY_COUNTER_OFF=1. Does NOT set DATABASE_URL
at import (the AIQ-1090 test-pollution lesson).
"""
from __future__ import annotations

import os

os.environ["RELOPASS_QUERY_COUNTER_OFF"] = "1"
os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")

from unittest import mock  # noqa: E402

import backend.main as bm  # noqa: E402


class _Conn:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, *a, **k):
        return None


def test_warmup_touches_db_supabase_and_executor():
    calls = {"db": 0, "sb": 0, "exec": 0}
    fake_engine = mock.MagicMock()
    fake_engine.connect.side_effect = lambda: (calls.__setitem__("db", calls["db"] + 1) or _Conn())
    fake_exec = mock.MagicMock()
    fake_exec.submit.side_effect = lambda *a, **k: calls.__setitem__("exec", calls["exec"] + 1)

    def _sb():
        calls["sb"] += 1
        return object()

    with mock.patch.object(bm.db, "engine", fake_engine), \
         mock.patch.object(bm, "_get_supabase_admin_client", _sb), \
         mock.patch.object(bm, "_hr_assign_side_effects_executor", fake_exec):
        bm._warmup_cold_paths()  # must not raise

    assert calls == {"db": 1, "sb": 1, "exec": 1}


def test_warmup_is_best_effort_when_every_step_raises():
    boom_engine = mock.MagicMock()
    boom_engine.connect.side_effect = RuntimeError("db down")
    boom_exec = mock.MagicMock()
    boom_exec.submit.side_effect = RuntimeError("pool down")

    def _sb_raise():
        raise RuntimeError("supabase down")

    with mock.patch.object(bm.db, "engine", boom_engine), \
         mock.patch.object(bm, "_get_supabase_admin_client", _sb_raise), \
         mock.patch.object(bm, "_hr_assign_side_effects_executor", boom_exec):
        # The critical guarantee: a warm-up failure never propagates (would crash startup).
        bm._warmup_cold_paths()

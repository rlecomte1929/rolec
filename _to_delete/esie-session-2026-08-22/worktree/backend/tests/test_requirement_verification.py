"""AIQ-1349 — per-requirement verification_status carry-through + expert-review enqueue."""
import os

os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

from backend.scripts.seed_requirements import build_payloads


def test_build_payloads_carries_file_level_verification_status():
    seed = {
        "verification_status": "corpus_grounded",
        "purposes_by_country": {"FRANCE": ["employment"]},
        "requirements": [{
            "key": "x", "pillar": "RESIDENCE", "severity": "WARN", "owner": "EMPLOYEE",
            "countries": {"FRANCE": {"title": "T", "description": "D. Indicative — confirm."}},
        }],
    }
    rows = build_payloads(seed)
    assert rows and all(r["verification_status"] == "corpus_grounded" for r in rows)


def test_build_payloads_defaults_representative():
    seed = {
        "purposes_by_country": {"FRANCE": ["employment"]},
        "requirements": [{
            "key": "x", "pillar": "IDENTITY", "severity": "BLOCKER", "owner": "EMPLOYEE",
            "countries": {"FRANCE": {"title": "T", "description": "D."}},
        }],
    }
    assert build_payloads(seed)[0]["verification_status"] == "representative"


# ── expert-verification enqueue ──
class _Resp:
    def __init__(self, data):
        self.data = data


class _Q:
    def __init__(self, t):
        self.t = t

    def select(self, *a, **k):
        return self

    def eq(self, *a, **k):
        return self

    def in_(self, *a, **k):
        return self

    def limit(self, *a, **k):
        return self

    def execute(self):
        return _Resp([])  # no existing → not deduped

    def insert(self, row):
        self.t.inserted.append(row)
        return _InsExec(row)


class _InsExec:
    def __init__(self, row):
        self._row = dict(row, id="q-1")

    def execute(self):
        return _Resp([self._row])


class _Table:
    def __init__(self):
        self.inserted = []


class _SB:
    def __init__(self):
        self.t = _Table()

    def table(self, _n):
        return _Q(self.t)


def test_enqueue_expert_verification_creates_item(monkeypatch):
    import backend.app.services.review_queue_service as rq
    sb = _SB()
    monkeypatch.setattr(rq, "_get_supabase", lambda: sb)
    monkeypatch.setattr(rq, "evaluate_queue_notification_rules", lambda *a, **k: None, raising=False)
    out = rq.create_queue_item_from_requirement_verification("FRANCE", "corpus_grounded")
    assert out and out["queue_item_type"] == "requirement_expert_verification"
    assert sb.t.inserted and sb.t.inserted[0]["country_code"] == "FRANCE"
    assert sb.t.inserted[0]["created_from_signal_id"] == "FRANCE"

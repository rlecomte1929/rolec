"""Regression: GET /api/notifications 500s when user_id is a legacy text id.

Found by /qa on 2026-09-12
Report: .gstack/qa-reports/qa-report-relopass-com-2026-09-12.md

Prod column notifications.user_id is uuid. ReloPass HR ids are strings like
seed-hr-testingapril. Equality without ::text raises:
invalid input syntax for type uuid.
"""
from pathlib import Path


def test_list_and_count_compare_user_id_as_text() -> None:
    src = Path(__file__).resolve().parents[1] / "db" / "support.py"
    text = src.read_text()
    assert "FROM notifications WHERE user_id::text = :uid" in text
    assert "WHERE user_id::text = :uid AND read_at IS NULL" in text
    assert "AND user_id::text = :uid" in text
    assert "FROM notifications WHERE user_id = :uid" not in text

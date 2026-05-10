"""API tests for collaboration endpoints - requires auth."""
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def _admin_token() -> str:
    res = client.post(
        "/api/auth/login",
        json={"identifier": "admin@relopass.com", "password": "Passw0rd!"},
    )
    assert res.status_code == 200
    return res.json()["token"]


def test_collaboration_requires_admin():
    res = client.get(
        "/api/admin/collaboration/threads/by-target",
        params={"target_type": "review_queue_item", "target_id": "test-id"},
    )
    assert res.status_code == 401


def test_collaboration_get_thread_as_admin():
    token = _admin_token()
    res = client.get(
        "/api/admin/collaboration/threads/by-target",
        params={"target_type": "review_queue_item", "target_id": "00000000-0000-0000-0000-000000000001"},
        headers={"Authorization": f"Bearer {token}"},
    )
    # 200 with thread null (no thread exists) or thread object
    assert res.status_code == 200
    data = res.json()
    assert "thread" in data


def test_collaboration_unread_count_as_admin():
    token = _admin_token()
    res = client.get(
        "/api/admin/collaboration/notifications/unread-count",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert "count" in res.json()


def test_collaboration_batch_summaries_as_admin():
    token = _admin_token()
    res = client.post(
        "/api/admin/collaboration/threads/summaries",
        json={"targets": [{"target_type": "review_queue_item", "target_id": "test-1"}]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert "summaries" in res.json()

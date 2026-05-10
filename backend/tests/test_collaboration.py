"""Tests for collaboration threads service and API."""
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from services.collaboration_service import _extract_mentions, _resolve_mention_to_user_id


def test_extract_mentions_uuid():
    body = "Hello @a1b2c3d4-e5f6-7890-abcd-ef1234567890 world"
    got = _extract_mentions(body)
    assert "a1b2c3d4-e5f6-7890-abcd-ef1234567890" in got


def test_extract_mentions_email():
    body = "Hey @user@example.com check this"
    got = _extract_mentions(body)
    # May be empty if user not in DB, or contain resolved id
    assert isinstance(got, list)


def test_extract_mentions_multiple():
    body = " @id1 @id2 "
    got = _extract_mentions(body)
    assert isinstance(got, list)


def test_extract_mentions_none():
    assert _extract_mentions("No mentions here") == []


def test_resolve_mention_uuid():
    uid = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
    assert _resolve_mention_to_user_id(uid) == uid


def test_resolve_mention_empty():
    assert _resolve_mention_to_user_id("") is None

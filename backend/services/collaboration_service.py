"""
Collaboration Service: threads and comments for internal admin discussion.
Admin-only. Attaches to queue items, notifications, staged candidates, live resources/events.
"""
from __future__ import annotations

import re
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .supabase_client import get_supabase_admin_client

log = logging.getLogger(__name__)

_ALLOWED_TARGET_TYPES = {
    "review_queue_item",
    "ops_notification",
    "staged_resource_candidate",
    "staged_event_candidate",
    "live_resource",
    "live_event",
}


def _get_supabase():
    return get_supabase_admin_client()


def _resolve_mention_to_user_id(mention: str) -> Optional[str]:
    """Resolve @email or @uuid to user id. Returns None if not found."""
    if not mention:
        return None
    # Already a UUID
    if re.match(r"^[a-f0-9-]{36}$", mention, re.I):
        return mention
    # Email - resolve via db
    try:
        from ..database import db
        user = db.get_user_by_email(mention)
        if user and user.get("id"):
            return user["id"]
        profiles = db.list_profiles(None) or []
        for p in profiles:
            if (p.get("email") or "").strip().lower() == mention.strip().lower():
                return p.get("id")
    except Exception:
        pass
    return None


def _extract_mentions(body: str) -> List[str]:
    """Extract @user_id or @email patterns. Returns resolved user ids."""
    matches = re.findall(r"@([a-zA-Z0-9_.-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]+)|@([a-f0-9-]{36})", body)
    raw = [m[0] or m[1] for m in matches if m[0] or m[1]]
    resolved = []
    seen = set()
    for r in raw:
        uid = _resolve_mention_to_user_id(r)
        if uid and uid not in seen:
            resolved.append(uid)
            seen.add(uid)
    return resolved


def _can_access_target(target_type: str, target_id: str, user_id: str) -> bool:
    """Check if user can access the target object. Admin can access all."""
    if target_type not in _ALLOWED_TARGET_TYPES:
        return False
    # For now, admin-only - any authenticated admin can access
    return True


def get_or_create_thread(
    target_type: str,
    target_id: str,
    actor_user_id: str,
    title: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Get existing thread or create new one for target."""
    if target_type not in _ALLOWED_TARGET_TYPES or not target_id:
        return None
    if not _can_access_target(target_type, target_id, actor_user_id):
        return None

    supabase = _get_supabase()
    existing = (
        supabase.table("collaboration_threads")
        .select("*")
        .eq("thread_target_type", target_type)
        .eq("thread_target_id", target_id)
        .limit(1)
        .execute()
    ).data

    if existing:
        return _enrich_thread(existing[0], actor_user_id)

    now = datetime.now(timezone.utc).isoformat()
    row = {
        "thread_target_type": target_type,
        "thread_target_id": target_id,
        "title": title or f"Discussion on {target_type}",
        "status": "open",
        "created_by_user_id": actor_user_id,
    }
    r = supabase.table("collaboration_threads").insert(row).execute()
    t = (r.data or [{}])[0]
    if t.get("id"):
        supabase.table("collaboration_thread_participants").insert({
            "thread_id": t["id"],
            "user_id": actor_user_id,
            "role_in_thread": "author",
        }).execute()
    return _enrich_thread(t, actor_user_id)


def get_thread_by_id(thread_id: str, actor_user_id: str) -> Optional[Dict[str, Any]]:
    """Get thread by id. Verifies access via target."""
    supabase = _get_supabase()
    r = (
        supabase.table("collaboration_threads")
        .select("*")
        .eq("id", thread_id)
        .limit(1)
        .execute()
    )
    items = r.data or []
    if not items:
        return None
    t = items[0]
    if not _can_access_target(t.get("thread_target_type", ""), t.get("thread_target_id", ""), actor_user_id):
        return None
    return _enrich_thread(t, actor_user_id)


def get_thread_for_target(
    target_type: str,
    target_id: str,
    actor_user_id: str,
) -> Optional[Dict[str, Any]]:
    """Get thread for target if exists."""
    if target_type not in _ALLOWED_TARGET_TYPES or not target_id:
        return None
    if not _can_access_target(target_type, target_id, actor_user_id):
        return None

    supabase = _get_supabase()
    r = (
        supabase.table("collaboration_threads")
        .select("*")
        .eq("thread_target_type", target_type)
        .eq("thread_target_id", target_id)
        .limit(1)
        .execute()
    )
    items = r.data or []
    if not items:
        return None
    return _enrich_thread(items[0], actor_user_id)


def _enrich_thread(t: Dict[str, Any], actor_user_id: str) -> Dict[str, Any]:
    """Add unread state and other computed fields."""
    supabase = _get_supabase()
    part = (
        supabase.table("collaboration_thread_participants")
        .select("last_read_at")
        .eq("thread_id", t["id"])
        .eq("user_id", actor_user_id)
        .limit(1)
        .execute()
    ).data
    last_read = part[0]["last_read_at"] if part else None
    last_comment = t.get("last_comment_at")
    t["is_unread"] = bool(last_comment and (not last_read or (last_comment > last_read if isinstance(last_comment, str) and isinstance(last_read, str) else True)))
    return t


def list_comments(thread_id: str, actor_user_id: str) -> List[Dict[str, Any]]:
    """List comments for thread, root first then replies."""
    thread = get_thread_by_id(thread_id, actor_user_id)
    if not thread:
        return []

    supabase = _get_supabase()
    r = (
        supabase.table("collaboration_comments")
        .select("*")
        .eq("thread_id", thread_id)
        .is_("deleted_at", "null")
        .order("created_at", desc=False)
        .execute()
    )
    comments = r.data or []

    # Fetch mentions and author display names per comment
    for c in comments:
        ments = (
            supabase.table("collaboration_comment_mentions")
            .select("mentioned_user_id")
            .eq("comment_id", c["id"])
            .execute()
        ).data or []
        c["mentions"] = [m["mentioned_user_id"] for m in ments]
        c["can_edit"] = c.get("author_user_id") == actor_user_id
        c["can_delete"] = c.get("author_user_id") == actor_user_id
        aid = c.get("author_user_id")
        if aid:
            try:
                from ..database import db
                profile = db.get_profile_record(aid)
                if profile:
                    c["author_display_name"] = profile.get("full_name") or profile.get("email") or aid[:8] + "…"
                    c["author_email"] = profile.get("email")
                else:
                    user = db.get_user_by_id(aid)
                    c["author_display_name"] = (user and (user.get("email") or user.get("name"))) or aid[:8] + "…"
                    c["author_email"] = user.get("email") if user else None
            except Exception:
                c["author_display_name"] = aid[:8] + "…"
                c["author_email"] = None
        else:
            c["author_display_name"] = "Unknown"
            c["author_email"] = None

    return comments


def create_comment(
    thread_id: str,
    body: str,
    actor_user_id: str,
    parent_comment_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Create comment. Creates thread if needed for target - but thread must exist here."""
    thread = get_thread_by_id(thread_id, actor_user_id)
    if not thread:
        return None
    if thread.get("status") == "closed":
        return None

    supabase = _get_supabase()
    now = datetime.now(timezone.utc).isoformat()
    row = {
        "thread_id": thread_id,
        "parent_comment_id": parent_comment_id,
        "author_user_id": actor_user_id,
        "body": (body or "").strip()[:10000],
        "body_format": "plain_text",
    }
    r = supabase.table("collaboration_comments").insert(row).execute()
    c = (r.data or [{}])[0]
    if not c.get("id"):
        return None

    # Persist mentions
    mention_ids = _extract_mentions(body)
    for mid in mention_ids[:20]:  # limit
        try:
            supabase.table("collaboration_comment_mentions").insert({
                "comment_id": c["id"],
                "mentioned_user_id": mid,
            }).execute()
            if mid != actor_user_id:
                _create_collab_notification(mid, "thread_mention", thread_id, c["id"], actor_user_id)
        except Exception:
            pass

    # Notify parent comment author on reply
    if parent_comment_id:
        parent = (
            supabase.table("collaboration_comments")
            .select("author_user_id")
            .eq("id", parent_comment_id)
            .limit(1)
            .execute()
        ).data
        if parent and parent[0].get("author_user_id") != actor_user_id:
            _create_collab_notification(
                parent[0]["author_user_id"], "thread_reply", thread_id, c["id"], actor_user_id
            )

    # Update thread
    supabase.table("collaboration_threads").update({
        "last_comment_at": now,
        "last_comment_by_user_id": actor_user_id,
        "comment_count": (thread.get("comment_count") or 0) + 1,
        "updated_at": now,
    }).eq("id", thread_id).execute()

    # Upsert participant
    _upsert_participant(thread_id, actor_user_id, "participant")
    c["mentions"] = mention_ids
    c["can_edit"] = True
    c["can_delete"] = True
    return c


def _create_collab_notification(
    user_id: str,
    notification_type: str,
    thread_id: str,
    comment_id: Optional[str],
    actor_user_id: Optional[str],
) -> None:
    """Create user-targeted collaboration notification."""
    try:
        supabase = _get_supabase()
        supabase.table("collaboration_notifications").insert({
            "user_id": user_id,
            "notification_type": notification_type,
            "thread_id": thread_id,
            "comment_id": comment_id,
            "actor_user_id": actor_user_id,
        }).execute()
    except Exception:
        pass


def _upsert_participant(thread_id: str, user_id: str, role: str):
    supabase = _get_supabase()
    existing = (
        supabase.table("collaboration_thread_participants")
        .select("id")
        .eq("thread_id", thread_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    ).data
    now = datetime.now(timezone.utc).isoformat()
    if existing:
        supabase.table("collaboration_thread_participants").update({
            "role_in_thread": role,
            "updated_at": now,
        }).eq("thread_id", thread_id).eq("user_id", user_id).execute()
    else:
        supabase.table("collaboration_thread_participants").insert({
            "thread_id": thread_id,
            "user_id": user_id,
            "role_in_thread": role,
            "is_subscribed": True,
        }).execute()


def edit_comment(comment_id: str, body: str, actor_user_id: str) -> Optional[Dict[str, Any]]:
    """Edit own comment."""
    supabase = _get_supabase()
    r = (
        supabase.table("collaboration_comments")
        .select("*")
        .eq("id", comment_id)
        .is_("deleted_at", "null")
        .limit(1)
        .execute()
    )
    items = r.data or []
    if not items or items[0].get("author_user_id") != actor_user_id:
        return None

    now = datetime.now(timezone.utc).isoformat()
    supabase.table("collaboration_comments").update({
        "body": (body or "").strip()[:10000],
        "is_edited": True,
        "edited_at": now,
        "updated_at": now,
    }).eq("id", comment_id).execute()

    # Update mentions
    supabase.table("collaboration_comment_mentions").delete().eq("comment_id", comment_id).execute()
    for mid in _extract_mentions(body)[:20]:
        try:
            supabase.table("collaboration_comment_mentions").insert({
                "comment_id": comment_id,
                "mentioned_user_id": mid,
            }).execute()
        except Exception:
            pass

    return (
        supabase.table("collaboration_comments")
        .select("*")
        .eq("id", comment_id)
        .limit(1)
        .execute()
    ).data[0]


def delete_comment(comment_id: str, actor_user_id: str) -> bool:
    """Soft-delete own comment."""
    supabase = _get_supabase()
    r = (
        supabase.table("collaboration_comments")
        .select("id, thread_id, author_user_id")
        .eq("id", comment_id)
        .is_("deleted_at", "null")
        .limit(1)
        .execute()
    )
    items = r.data or []
    if not items or items[0].get("author_user_id") != actor_user_id:
        return False

    now = datetime.now(timezone.utc).isoformat()
    supabase.table("collaboration_comments").update({
        "deleted_at": now,
        "deleted_by_user_id": actor_user_id,
        "updated_at": now,
    }).eq("id", comment_id).execute()

    # Decrement thread comment count
    thread_id = items[0].get("thread_id")
    if thread_id:
        thread = (
            supabase.table("collaboration_threads")
            .select("comment_count")
            .eq("id", thread_id)
            .limit(1)
            .execute()
        ).data
        if thread:
            new_count = max(0, (thread[0].get("comment_count") or 1) - 1)
            supabase.table("collaboration_threads").update({
                "comment_count": new_count,
                "updated_at": now,
            }).eq("id", thread_id).execute()
    return True


def resolve_thread(thread_id: str, actor_user_id: str, note: Optional[str] = None) -> Optional[Dict[str, Any]]:
    thread = get_thread_by_id(thread_id, actor_user_id)
    if not thread or thread.get("status") != "open":
        return None

    now = datetime.now(timezone.utc).isoformat()
    supabase = _get_supabase()
    supabase.table("collaboration_threads").update({
        "status": "resolved",
        "resolved_by_user_id": actor_user_id,
        "resolved_at": now,
        "updated_at": now,
    }).eq("id", thread_id).execute()
    return get_thread_by_id(thread_id, actor_user_id)


def reopen_thread(thread_id: str, actor_user_id: str) -> Optional[Dict[str, Any]]:
    thread = get_thread_by_id(thread_id, actor_user_id)
    if not thread or thread.get("status") not in ("resolved", "closed"):
        return None

    now = datetime.now(timezone.utc).isoformat()
    supabase = _get_supabase()
    supabase.table("collaboration_threads").update({
        "status": "open",
        "resolved_by_user_id": None,
        "resolved_at": None,
        "updated_at": now,
    }).eq("id", thread_id).execute()
    # Notify participants that thread was reopened
    participants = (
        supabase.table("collaboration_thread_participants")
        .select("user_id")
        .eq("thread_id", thread_id)
        .execute()
    ).data or []
    for p in participants:
        uid = p.get("user_id")
        if uid and uid != actor_user_id:
            _create_collab_notification(uid, "thread_reopened", thread_id, None, actor_user_id)
    return get_thread_by_id(thread_id, actor_user_id)


def close_thread(thread_id: str, actor_user_id: str) -> Optional[Dict[str, Any]]:
    thread = get_thread_by_id(thread_id, actor_user_id)
    if not thread:
        return None

    now = datetime.now(timezone.utc).isoformat()
    supabase = _get_supabase()
    supabase.table("collaboration_threads").update({
        "status": "closed",
        "updated_at": now,
    }).eq("id", thread_id).execute()
    return get_thread_by_id(thread_id, actor_user_id)


def mark_thread_read(thread_id: str, actor_user_id: str, last_comment_id: Optional[str] = None) -> bool:
    thread = get_thread_by_id(thread_id, actor_user_id)
    if not thread:
        return False

    now = datetime.now(timezone.utc).isoformat()
    supabase = _get_supabase()
    part = (
        supabase.table("collaboration_thread_participants")
        .select("id")
        .eq("thread_id", thread_id)
        .eq("user_id", actor_user_id)
        .limit(1)
        .execute()
    ).data
    if part:
        supabase.table("collaboration_thread_participants").update({
            "last_read_comment_id": last_comment_id,
            "last_read_at": now,
            "updated_at": now,
        }).eq("thread_id", thread_id).eq("user_id", actor_user_id).execute()
    else:
        supabase.table("collaboration_thread_participants").insert({
            "thread_id": thread_id,
            "user_id": actor_user_id,
            "last_read_comment_id": last_comment_id,
            "last_read_at": now,
        }).execute()
    return True


def get_thread_summary_for_target(
    target_type: str,
    target_id: str,
    actor_user_id: str,
) -> Optional[Dict[str, Any]]:
    """Lightweight summary: comment count, last_comment_at, has_unread."""
    t = get_thread_for_target(target_type, target_id, actor_user_id)
    if not t:
        return None
    return {
        "thread_id": t.get("id"),
        "comment_count": t.get("comment_count", 0),
        "last_comment_at": t.get("last_comment_at"),
        "status": t.get("status"),
        "is_unread": t.get("is_unread", False),
    }


def get_collaboration_unread_count(user_id: str) -> int:
    """Count unread collaboration notifications for user."""
    try:
        supabase = _get_supabase()
        r = (
            supabase.table("collaboration_notifications")
            .select("id")
            .eq("user_id", user_id)
            .is_("read_at", "null")
            .limit(999)
            .execute()
        )
        return len(r.data or [])
    except Exception:
        return 0


def list_all_threads(
    actor_user_id: str,
    *,
    target_type: Optional[str] = None,
    participant_user_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    """List all collaboration threads for admin. Optional filters: target_type, participant, status."""
    supabase = _get_supabase()
    q = supabase.table("collaboration_threads").select("*")
    if target_type:
        q = q.eq("thread_target_type", target_type)
    if status:
        q = q.eq("status", status)
    q = q.order("last_comment_at", desc=True, nullsfirst=False)
    q = q.range(offset, offset + limit - 1)
    rows = q.execute().data or []
    out = []
    for t in rows:
        # Resolve participants
        part_rows = (
            supabase.table("collaboration_thread_participants")
            .select("user_id, role_in_thread")
            .eq("thread_id", t["id"])
            .execute()
        ).data or []
        if participant_user_id and not any(p.get("user_id") == participant_user_id for p in part_rows):
            continue
        participant_ids = [p["user_id"] for p in part_rows]
        participant_names = []
        for pid in participant_ids[:5]:
            try:
                from ..database import db
                prof = db.get_profile_record(pid)
                if prof:
                    participant_names.append(prof.get("full_name") or prof.get("email") or pid[:8] + "…")
                else:
                    u = db.get_user_by_id(pid)
                    participant_names.append((u and (u.get("email") or u.get("name"))) or pid[:8] + "…")
            except Exception:
                participant_names.append(pid[:8] + "…")
        last_body = None
        if t.get("last_comment_at"):
            comm = (
                supabase.table("collaboration_comments")
                .select("body")
                .eq("thread_id", t["id"])
                .is_("deleted_at", "null")
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            ).data
            if comm:
                last_body = (comm[0].get("body") or "")[:100]
                if len((comm[0].get("body") or "")) > 100:
                    last_body = last_body.rstrip() + "…"
        first_participant_id = participant_ids[0] if participant_ids else None
        first_participant_name = participant_names[0] if participant_names else "—"
        out.append({
            "thread_id": t["id"],
            "thread_type": "collaboration",
            "target_type": t.get("thread_target_type"),
            "target_id": t.get("thread_target_id"),
            "title": t.get("title"),
            "status": t.get("status"),
            "participant_id": first_participant_id,
            "participant_name": first_participant_name,
            "participant_role": "collaboration",
            "participants": participant_names or ["—"],
            "last_message_preview": last_body or "—",
            "last_message_at": t.get("last_comment_at"),
            "message_count": t.get("comment_count", 0),
            "created_at": t.get("created_at"),
        })
    return out


def get_thread_summaries_batch(
    targets: List[Dict[str, str]],
    actor_user_id: str,
) -> Dict[str, Dict[str, Any]]:
    """Batch fetch summaries. targets: [{target_type, target_id}]. Returns key by target_id."""
    result: Dict[str, Dict[str, Any]] = {}
    for t in targets[:100]:  # limit
        tt = t.get("target_type")
        tid = t.get("target_id")
        if not tt or not tid:
            continue
        s = get_thread_summary_for_target(tt, tid, actor_user_id)
        if s:
            result[tid] = s
    return result

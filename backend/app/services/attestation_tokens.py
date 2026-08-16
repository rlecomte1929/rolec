"""Token minting/verification and content hashing for counsel attestation.

Isolated from the router so the security-critical primitives are unit-testable without
mounting FastAPI, and so there is exactly ONE place that knows how a token becomes a hash.

Three rules this module exists to enforce:

**The raw token is never stored.** `mint_token()` returns the raw token and its SHA-256;
only the hash reaches the database. A dump of `corridor_attestation_requests` therefore
yields no working reviewer links. The raw value is shown to the admin once, at creation,
and is unrecoverable afterwards — re-issue means a new token, which is the correct
security property even though it is mildly inconvenient.

**Lookup is by hash, compared in constant time.** `hash_token()` is deterministic, so the
lookup is an indexed equality on `link_token_hash`. `tokens_match()` wraps
`hmac.compare_digest` for any place that compares two hashes directly, so a timing side
channel cannot be used to walk a hash byte by byte.

**The content hash is canonical.** `content_hash()` sorts keys and pins separators before
hashing, so the same checklist always produces the same digest regardless of dict ordering
or Python version. This matters more than it looks: the hash is what a signature is bound
to, and `POST /sign` rejects a mismatch with 409. If the hash were order-dependent, a
reviewer could be refused their own signature because a dict iterated differently — or,
worse, a genuinely changed checklist could hash the same and slip through.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
from typing import Any, Dict, List, Tuple

#: `secrets.token_urlsafe(32)` yields 43 URL-safe base64 chars. Accept a small range rather
#: than pinning 43 exactly, so the length can be raised later without a flag day.
_TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{32,128}$")

#: Bytes of entropy per token. 32 bytes = 256 bits — brute force is not the attack here.
TOKEN_BYTES = 32

#: How long a reviewer link stays live. Attestation is a considered legal review, not a
#: password reset, so weeks rather than minutes; but it must still expire.
DEFAULT_TOKEN_TTL_DAYS = 30


def mint_token() -> Tuple[str, str]:
    """Return `(raw_token, token_hash)`. Persist ONLY the hash.

    The caller must return `raw_token` to the admin exactly once and never write it
    anywhere — not to the database, not to a log line.
    """
    raw = secrets.token_urlsafe(TOKEN_BYTES)
    return raw, hash_token(raw)


def is_well_formed(token: str) -> bool:
    """Cheap shape check, run BEFORE hashing or touching the database.

    Rejects the obvious junk (empty, oversized, path traversal, SQL-ish payloads) without
    a query, which keeps an enumeration attempt from costing a database round trip each.
    """
    return bool(token) and bool(_TOKEN_RE.match(token))


def hash_token(token: str) -> str:
    """SHA-256 hex of a raw token — the value stored in `link_token_hash`.

    Plain SHA-256 rather than a slow KDF on purpose: this is a 256-bit random token, not a
    user-chosen password. There is no dictionary to attack, so key stretching would buy
    nothing and cost latency on every public request.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def tokens_match(a: str, b: str) -> bool:
    """Constant-time comparison of two token hashes.

    An empty or missing hash never matches — not even another empty one. A draft request
    has `link_token_hash IS NULL`, and letting NULL == NULL succeed would make every
    un-tokenized draft openable by anyone who sent no token at all.
    """
    if not a or not b:
        return False
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


def canonical_payload(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Normalise the checklist to exactly the fields a signature is bound to.

    Deliberately a WHITELIST, not a copy-with-deletions. The snapshot is handed to an
    external party, so a field can only appear here by being named — a new PII-bearing
    column on `requirement_items` cannot leak into the envelope by default. This is the
    same boundary the public router asserts, enforced one layer lower.
    """
    return [
        {
            "requirement_item_id": str(item.get("requirement_item_id") or ""),
            "title": item.get("title") or "",
            "claim": item.get("claim") or "",
            "source_url": item.get("source_url") or "",
            "evidence": item.get("evidence") or "",
        }
        for item in items
    ]


def content_hash(items: List[Dict[str, Any]]) -> str:
    """SHA-256 of the canonical checklist JSON.

    `sort_keys=True` plus fixed separators makes the digest independent of dict insertion
    order; the item list is sorted by `requirement_item_id` so re-fetching the corridor in
    a different row order does not invalidate a live signature.
    """
    payload = sorted(canonical_payload(items), key=lambda i: i["requirement_item_id"])
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()

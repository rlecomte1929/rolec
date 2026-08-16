"""Token minting/hashing and content-hash canonicalisation for counsel attestation.

These are the security primitives the whole feature rests on, so they are tested without
FastAPI in the way: if `content_hash` is order-dependent, the 409 mismatch guard on
`POST /sign` becomes a coin flip, and no router test would tell you why.
"""
import json

from backend.app.services.attestation_tokens import (
    DEFAULT_TOKEN_TTL_DAYS,
    canonical_payload,
    content_hash,
    hash_token,
    is_well_formed,
    mint_token,
    tokens_match,
)


def _items():
    return [
        {"requirement_item_id": "b-2", "title": "Skattekort", "claim": "Before first salary",
         "source_url": "https://skatteetaten.no/x", "evidence": "quote b"},
        {"requirement_item_id": "a-1", "title": "D-number", "claim": "Stays under 6 months",
         "source_url": "https://skatteetaten.no/y", "evidence": "quote a"},
    ]


# ── minting ──────────────────────────────────────────────────────────────────────────

def test_mint_returns_a_raw_token_and_its_hash_and_they_differ():
    raw, digest = mint_token()
    assert is_well_formed(raw)
    assert digest == hash_token(raw)
    assert raw != digest
    # 64 hex chars — a full SHA-256, not a truncation.
    assert len(digest) == 64 and all(c in "0123456789abcdef" for c in digest)


def test_every_token_is_unique():
    """A repeat would mean the RNG is broken, and the UNIQUE index would 500 on insert."""
    tokens = {mint_token()[0] for _ in range(200)}
    assert len(tokens) == 200


def test_the_raw_token_is_not_recoverable_from_the_hash():
    """The point of storing only the hash: a DB dump yields no working links."""
    raw, digest = mint_token()
    assert raw not in digest
    # And the hash is deterministic, so lookup by hash works.
    assert hash_token(raw) == digest


# ── shape validation ─────────────────────────────────────────────────────────────────

def test_malformed_tokens_are_rejected_before_any_db_work():
    for bad in ["", "   ", "short", "../../etc/passwd", "a" * 200,
                "abc'; DROP TABLE corridor_attestation_requests;--",
                "has spaces in it aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", None]:
        assert not is_well_formed(bad), f"{bad!r} should be rejected"


def test_a_freshly_minted_token_is_well_formed():
    for _ in range(50):
        assert is_well_formed(mint_token()[0])


# ── constant-time compare ────────────────────────────────────────────────────────────

def test_tokens_match_is_correct():
    a = hash_token("x" * 40)
    assert tokens_match(a, a)
    assert not tokens_match(a, hash_token("y" * 40))


def test_an_empty_or_missing_hash_never_matches_even_another_empty_one():
    """A draft request has link_token_hash IS NULL.

    If NULL == NULL succeeded, every un-tokenized draft would be openable by a caller who
    supplied no token at all — the emptiest possible credential unlocking the newest rows.
    """
    assert not tokens_match("", "")
    assert not tokens_match(None, None)
    assert not tokens_match(None, hash_token("x" * 40))
    assert not tokens_match(hash_token("x" * 40), None)
    assert not tokens_match(hash_token("x" * 40), "")


# ── content hash ─────────────────────────────────────────────────────────────────────

def test_content_hash_is_stable_across_item_order():
    """A re-fetch in a different row order must not invalidate a live signature."""
    items = _items()
    assert content_hash(items) == content_hash(list(reversed(items)))


def test_content_hash_is_stable_across_key_order():
    """Dict insertion order must not change the digest."""
    a = [{"requirement_item_id": "a-1", "title": "T", "claim": "C", "source_url": "U", "evidence": "E"}]
    b = [{"evidence": "E", "source_url": "U", "claim": "C", "title": "T", "requirement_item_id": "a-1"}]
    assert content_hash(a) == content_hash(b)


def test_content_hash_changes_when_a_claim_changes():
    """The whole 409 guard depends on this actually discriminating."""
    items = _items()
    mutated = json.loads(json.dumps(items))
    mutated[0]["claim"] = "Something counsel never reviewed"
    assert content_hash(items) != content_hash(mutated)


def test_content_hash_changes_when_an_item_is_added_or_removed():
    items = _items()
    assert content_hash(items) != content_hash(items[:1])
    extra = items + [{"requirement_item_id": "c-3", "title": "New", "claim": "c",
                      "source_url": "u", "evidence": "e"}]
    assert content_hash(items) != content_hash(extra)


def test_canonical_payload_is_a_whitelist_not_a_deletion():
    """A new PII-bearing column must not be able to leak into the envelope by default."""
    leaky = [{
        "requirement_item_id": "a-1", "title": "T", "claim": "C",
        "source_url": "U", "evidence": "E",
        # every one of these must be dropped
        "employee_email": "someone@example.com", "case_id": "case-123",
        "company_id": "co-9", "full_name": "A Person", "passport_number": "X1234567",
    }]
    out = canonical_payload(leaky)
    assert set(out[0].keys()) == {"requirement_item_id", "title", "claim", "source_url", "evidence"}
    blob = json.dumps(out)
    for forbidden in ["someone@example.com", "case-123", "co-9", "A Person", "X1234567"]:
        assert forbidden not in blob


def test_ttl_default_is_finite():
    """An attestation link that never expires is a standing credential."""
    assert 0 < DEFAULT_TOKEN_TTL_DAYS <= 90

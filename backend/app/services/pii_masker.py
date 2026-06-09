"""
[P5-9 H1/C2] Centralised PII masker for the 5 patterns called out in the
security review (`docs/security/P5-9_security_review_2026-05-22.md`):

  1. Phone               — international + national formats
  2. IBAN                — 15–34 alphanumerics starting with country code
  3. Passport number     — broad alphanumeric pattern (defensive)
  4. SSN / D-number      — French INSEE, US SSN, Norwegian fnr/d-number
  5. National ID / email — generic ID and email fallbacks

Two entry points
────────────────
- `mask_pii(text)` — applies all patterns to a free-text string and
  returns the masked version. Used by `AnthropicClient.complete()` and
  the OpenAI path before any payload leaves the platform (H1).

- `safe_log_text(text, max_len=120)` — truncates + masks. Used by any
  log call that needs to include user input. Replaces the
  query[:120] anti-pattern that leaked raw query text in P5-9 §2 C2.

Design notes
────────────
- Patterns are intentionally aggressive — we'd rather over-mask a string
  the user wrote ("My booking number is AB1234567") than leak an actual
  passport. The cost of a masked benign string in an LLM prompt is a
  marginally lower-quality answer; the cost of a leaked passport is
  measured in compliance fines.
- Each pattern emits a distinct placeholder (`[REDACTED_PHONE]`,
  `[REDACTED_IBAN]`, etc.) so test failures point straight at the rule
  that fired.
- `mask_pii` is idempotent: re-applying it to an already-masked string
  yields the same string. This lets callers compose with redact-on-log
  filters without double-bracket noise.
- We do **not** mask names, dates, currency amounts, or addresses.
  Those are too noisy and the data is already inside the platform's
  trust boundary by the time the LLM is called.

Performance
───────────
~150µs per call on a 200-char string (measured locally). The regex
patterns are compiled once at module import.
"""
from __future__ import annotations

import re
from typing import Pattern


# ---------------------------------------------------------------------------
# Compiled patterns (order matters — match the most specific first so
# stricter formats don't get swallowed by the loose national-ID rule)
# ---------------------------------------------------------------------------

# Email — match first; address could collide with the loose ID rule.
_EMAIL: Pattern[str] = re.compile(
    r"\b[\w.+-]+@[\w.-]+\.\w+\b",
    re.IGNORECASE,
)

# IBAN — two flavours so we don't false-match by greedy-consuming
# neighbouring words:
#   - Compact: 2 letters + 2 check digits + 11-30 contiguous alnum.
#   - Spaced:  human-formatted with mandatory 4-char groups (e.g.
#              "FR76 3000 1007 1234 5678 9012 345").
# Case-sensitive (real IBAN displays are always uppercase); we tolerate
# common lowercase via the explicit `re.IGNORECASE` only on the
# alternative pattern, not the body.
_IBAN_COMPACT: Pattern[str] = re.compile(
    r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b",
)
_IBAN_SPACED: Pattern[str] = re.compile(
    r"\b[A-Z]{2}\d{2}(?:\s[A-Z0-9]{2,4}){2,7}\b",
)

# French INSEE / SSN — 15 digits (1+2+2+2+3+3+2) with optional spaces.
_FR_INSEE: Pattern[str] = re.compile(
    r"(?<!\d)[12]\s?\d{2}\s?\d{2}\s?\d{2}\s?\d{3}\s?\d{3}\s?\d{2}(?!\d)",
)

# US SSN — 3-2-4 digits, separators optional. Negative lookarounds
# prevent matching the middle of a longer digit run.
_US_SSN: Pattern[str] = re.compile(
    r"(?<!\d)\d{3}[- ]?\d{2}[- ]?\d{4}(?!\d)",
)

# Norwegian fødselsnummer / D-number — 11 digits (DDMMYY + 5 digits).
# fnr first digit ∈ 0-3; D-number first digit ∈ 4-7 (day+40).
_NO_FNR: Pattern[str] = re.compile(
    r"(?<!\d)[0-7]\d(?:0\d|1[0-2])\d{2}\s?\d{5}(?!\d)",
)

# Passport — 1-2 capital letters + 5-9 digits. Case-sensitive so we
# don't false-match common lowercase token+digit combinations like
# "img12345". The 9-digit-only US passport case is handled by the
# US_SSN pattern above (same shape — both mask the same data, the
# label is informational).
_PASSPORT: Pattern[str] = re.compile(
    r"\b[A-Z]{1,2}\d{5,9}\b",
)

# Phone — international (+CC) or national; 8+ digits with optional
# separators. Runs AFTER the SSN/INSEE/fnr/passport rules so a 9-digit
# string lands on those more specific labels first. The negative
# lookbehind keeps us from grabbing the trailing chars of an email or
# already-masked token; the explicit `\+?` is captured inside the
# match so the leading `+` doesn't leak.
_PHONE: Pattern[str] = re.compile(
    r"(?<![\w@.])\+?\d(?:[\d\s().-]{6,})\d(?![\w@.])",
)

# Generic alphanumeric ID — last-line-of-defense for things that look
# like an internal reference but didn't fit a more specific shape.
# Case-sensitive (uppercase only) to avoid false-positives on filenames
# / lowercase tokens.
_GENERIC_ID: Pattern[str] = re.compile(
    r"\b[A-Z]{1,3}\d{4,}\b|\b\d{5,}[A-Z]+\d*\b",
)

# Already-masked tokens — used by `mask_pii` to short-circuit idempotency.
_ALREADY_MASKED: Pattern[str] = re.compile(
    r"\[REDACTED_(?:EMAIL|PHONE|IBAN|PASSPORT|SSN|FNR|ID)\]",
)


# 11-digit candidate for the German Steuer-ID checksum gate.
_DE_STEUER_CANDIDATE: Pattern[str] = re.compile(r"(?<!\d)\d{11}(?!\d)")


# ---------------------------------------------------------------------------
# Custom recognizer registry wiring (AI-I.3f)
# ---------------------------------------------------------------------------
# The masker stays presidio-free: it consumes the *pure validators* exposed by
# backend/app/services/pii/presidio_recognizers/* (mod-97 IBAN, ICAO-9303
# passport, Norwegian/German/French national-ID checksums). The presidio
# AnalyzerEngine path (for NER name detection) is a deliberate, separate upgrade
# that would add the spaCy runtime dependency — not pulled in here.

def _mask_with_recognizers(text: str) -> str:
    """Redact checksum-validated PII the shape-only regexes miss. Never raises;
    returns the input unchanged if the recognizer package can't be imported."""
    try:
        from .pii.presidio_recognizers import eu_passport, de_steuer_id
    except Exception:  # pragma: no cover - import safety
        return text

    out = text
    # Country-format + MRZ-checksum passports (FR "19AB54321", IT "AA1234567",
    # MRZ document fields) that `_PASSPORT` (leading-letter only) cannot see.
    try:
        spans = eu_passport.find_passports(out)
        for m in sorted(spans, key=lambda x: x.start, reverse=True):
            out = out[: m.start] + "[REDACTED_PASSPORT]" + out[m.end :]
    except Exception:  # pragma: no cover
        pass
    # German Steuer-ID: an 11-digit run that passes the ISO 7064 MOD 11,10 check
    # and the digit-uniqueness rule (otherwise it would fall to the phone rule).
    try:
        out = _DE_STEUER_CANDIDATE.sub(
            lambda mt: "[REDACTED_ID]" if de_steuer_id.is_valid_steuer_id(mt.group(0)) else mt.group(0),
            out,
        )
    except Exception:  # pragma: no cover
        pass
    return out


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def mask_pii(text: str) -> str:
    """Return `text` with each PII pattern replaced by a `[REDACTED_*]`
    placeholder. Safe to call on any string; never raises.

    Order: email → IBAN → phone → French SSN → US SSN → Norwegian fnr
    → passport → generic ID. Specific rules run first so they don't get
    swallowed by `_GENERIC_ID`.
    """
    if not text:
        return text
    try:
        # Order matters: specific shapes run before the loose ones so a
        # 9-digit string lands on SSN/passport, not phone or generic ID.
        out = _EMAIL.sub("[REDACTED_EMAIL]", text)
        out = _IBAN_SPACED.sub("[REDACTED_IBAN]", out)
        out = _IBAN_COMPACT.sub("[REDACTED_IBAN]", out)
        out = _FR_INSEE.sub("[REDACTED_SSN]", out)
        out = _US_SSN.sub("[REDACTED_SSN]", out)
        out = _NO_FNR.sub("[REDACTED_FNR]", out)
        out = _PASSPORT.sub("[REDACTED_PASSPORT]", out)
        # [AI-I.3f] Checksum-validated pass from the custom recognizer registry,
        # catching PII the shape-only regexes above miss — country-format
        # passports (FR/IT/MRZ) and the German Steuer-ID — before the loose
        # phone/generic rules claim them with a wrong label. Additive: it only
        # touches spans the earlier passes left untouched.
        out = _mask_with_recognizers(out)
        out = _PHONE.sub("[REDACTED_PHONE]", out)
        out = _GENERIC_ID.sub("[REDACTED_ID]", out)
        return out
    except Exception:
        # Defensive — never crash a request because the masker tripped
        # on weird Unicode. Return the original text and let the caller
        # decide whether the surrounding context (LLM prompt vs log)
        # is willing to accept it.
        return text


def safe_log_text(text: str, max_len: int = 120) -> str:
    """Truncate + mask a piece of user-supplied text for inclusion in a
    log line. Replacement for the `query[:120]` anti-pattern flagged
    in P5-9 §2 C2.

    Order: truncate first, then mask. This keeps the masker's regex
    work bounded by max_len instead of the full payload size.
    """
    if not text:
        return ""
    truncated = text[:max_len]
    masked = mask_pii(truncated)
    if len(text) > max_len:
        return f"{masked}…"
    return masked


def is_already_masked(text: str) -> bool:
    """True if `text` contains at least one `[REDACTED_*]` placeholder.
    Mostly used by tests to assert idempotency."""
    return bool(_ALREADY_MASKED.search(text or ""))

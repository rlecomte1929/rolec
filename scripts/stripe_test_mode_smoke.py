#!/usr/bin/env python3
"""Stripe webhook TEST-MODE smoke check (Phase 7). Locally-signed — no Stripe CLI, no card.

Holds a copy of one STRIPE_WEBHOOK_SECRET value, so it can forge both valid and invalid
Stripe signatures and POST them at a running backend's /api/stripe/webhook. It asserts the
webhook's own {"status": ...} response, so it needs no database access.

Covers spec §8 tests #3 (tampered), #4 (unknown type), #5 (missing case_id) with no data
mutation; and, only when --case-id is given, #1 (applied) + #2 (duplicate replay), which
DO flip that case to access_tier='roadmap' — pass a disposable test case and reset it after.

TEST MODE ONLY. Refuses a prod API base-url. Never point this at prod.

    python scripts/stripe_test_mode_smoke.py --base-url http://localhost:8000 \
        --webhook-secret whsec_xxx [--case-id <disposable_relocation_cases_id>]
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import sys
import time
import urllib.error
import urllib.request
import uuid

_PROD_MARKERS = ("api.relopass.com", "rolec-eu", "onrender.com")


def _sign(payload: bytes, secret: str, ts: int) -> str:
    signed = f"{ts}.".encode() + payload
    digest = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    return f"t={ts},v1={digest}"


def _post(base_url: str, payload: bytes, sig_header: str):
    """POST to the webhook; return (status_code, parsed_json_or_None)."""
    req = urllib.request.Request(
        base_url.rstrip("/") + "/api/stripe/webhook",
        data=payload,
        method="POST",
        headers={"Content-Type": "application/json", "Stripe-Signature": sig_header},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            code, raw = resp.getcode(), resp.read()
    except urllib.error.HTTPError as e:
        code, raw = e.code, e.read()
    try:
        return code, json.loads(raw or b"{}")
    except json.JSONDecodeError:
        return code, None


def _event(event_type: str, *, event_id: str, metadata: dict) -> bytes:
    return json.dumps({
        "id": event_id,
        "type": event_type,
        "data": {"object": {"id": "cs_smoke", "amount_total": 80000, "currency": "eur",
                            "payment_intent": "pi_smoke", "metadata": metadata}},
    }).encode()


class Runner:
    def __init__(self, base_url: str, secret: str):
        self.base_url = base_url
        self.secret = secret
        self.failures = 0

    def check(self, name: str, ok: bool, detail: str = "") -> None:
        mark = "PASS" if ok else "FAIL"
        print(f"  [{mark}] {name}{(' — ' + detail) if detail else ''}")
        if not ok:
            self.failures += 1

    def send(self, payload: bytes, *, sign_payload: bytes | None = None):
        """Send payload; sign over sign_payload (defaults to payload). Tampered = differ."""
        ts = int(time.time())
        sig = _sign(sign_payload if sign_payload is not None else payload, self.secret, ts)
        return _post(self.base_url, payload, sig)

    # ── non-mutating ─────────────────────────────────────────────────────────
    def test_tampered_body(self):  # spec #3
        good = _event("checkout.session.completed", event_id=f"evt_{uuid.uuid4().hex}",
                      metadata={"case_id": "x", "tier": "roadmap"})
        tampered = good[:-1] + b" "  # one byte changed → signature no longer matches
        code, _ = self.send(tampered, sign_payload=good)
        self.check("#3 tampered body → 400", code == 400, f"got {code}")

    def test_unknown_type(self):  # spec #4
        code, body = self.send(_event("payment_intent.succeeded",
                                       event_id=f"evt_{uuid.uuid4().hex}", metadata={}))
        ok = code == 200 and (body or {}).get("status") == "ignored"
        self.check("#4 unknown event type → 200 ignored", ok, f"got {code} {body}")

    def test_missing_case_id(self):  # spec #5
        code, body = self.send(_event("checkout.session.completed",
                                       event_id=f"evt_{uuid.uuid4().hex}",
                                       metadata={"tier": "roadmap"}))  # no case_id
        ok = code == 200 and (body or {}).get("status") == "ignored" \
            and (body or {}).get("reason") == "missing_case_id"
        self.check("#5 missing metadata.case_id → 200 ignored", ok, f"got {code} {body}")

    # ── mutating (opt-in) ─────────────────────────────────────────────────────
    def test_applied_and_duplicate(self, case_id: str):  # spec #1 + #2
        eid = f"evt_{uuid.uuid4().hex}"
        payload = _event("checkout.session.completed", event_id=eid,
                         metadata={"case_id": case_id, "tier": "roadmap"})
        code, body = self.send(payload)
        ok = code == 200 and (body or {}).get("status") == "applied" \
            and (body or {}).get("tier") == "roadmap"
        self.check("#1 applied → 200 applied (tier flipped)", ok, f"got {code} {body}")

        # replay the SAME event id → duplicate, no second flip
        code2, body2 = self.send(payload)
        ok2 = code2 == 200 and (body2 or {}).get("status") == "duplicate"
        self.check("#2 duplicate replay → 200 duplicate", ok2, f"got {code2} {body2}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Stripe webhook test-mode smoke check")
    ap.add_argument("--base-url", required=True, help="backend base url, e.g. http://localhost:8000")
    ap.add_argument("--webhook-secret", required=True, help="a STRIPE_WEBHOOK_SECRET value the backend holds")
    ap.add_argument("--case-id", help="disposable relocation_cases id — enables the mutating #1/#2 tests")
    args = ap.parse_args()

    if any(m in args.base_url for m in _PROD_MARKERS):
        print(f"REFUSING: --base-url looks like prod ({args.base_url}). Test mode is local/staging only.",
              file=sys.stderr)
        return 2

    print(f"Stripe webhook smoke — {args.base_url}")
    r = Runner(args.base_url, args.webhook_secret)

    print("Non-mutating checks:")
    r.test_tampered_body()
    r.test_unknown_type()
    r.test_missing_case_id()

    if args.case_id:
        print(f"Mutating checks (flips case {args.case_id} → roadmap; reset it afterwards):")
        r.test_applied_and_duplicate(args.case_id)
    else:
        print("Mutating checks (#1 applied, #2 duplicate): SKIPPED — pass --case-id to run them.")

    print()
    if r.failures:
        print(f"RESULT: {r.failures} check(s) FAILED.")
        return 1
    print("RESULT: all checks PASSED.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

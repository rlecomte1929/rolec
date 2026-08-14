#!/usr/bin/env python3
"""Fail CI if a third-party ad pixel is added without a consent gate.

WHY
---
EU ad targeting is permitted for the ADS campaign on exactly one condition: no third-party
ad pixel runs on the landing pages. That is not a stylistic preference — ePrivacy Art. 5(3)
governs storing or accessing information on a visitor's device, which is precisely what an
ad pixel does, and it is the only thing that makes EU traffic legally different from US or
UK traffic. Interest-based targeting where we upload no customer data makes the ad platform
the controller, not us.

So the geography rule in docs/gtm/ADS-5_otto_campaign_brief.md reads:

    Geography: US, UK and EU permitted — for as long as no third-party ad pixel is
    installed.

A rule like that decays into fiction unless something measures it. On 2026-08-10 the ADS-4
gate "both URLs return prerendered HTML on the live domain" was sitting ticked while both
URLs served an empty shell to every crawler, because nobody ever ran the check. This script
exists so the geography condition cannot rot the same way.

WHAT IS AND ISN'T BANNED
------------------------
BANNED on the public/marketing surface: any third-party ad or conversion pixel — the
globals and script hosts listed below.

ALLOWED: our first-party analytics. `emitMarketingEvent` posts UTMs to our own
/api/public/track and to PostHog, which is already consent-gated
(`opt_out_capturing_by_default`). That is what ADS-4's attribution actually runs on, and it
needs no pixel.

IF YOU GENUINELY NEED A PIXEL
-----------------------------
Do not delete this check. Gate the pixel behind the existing ConsentBanner
(frontend/src/App.tsx, mounted globally so it already covers both ad landing pages) so it
loads only after `getAnalyticsConsent() === 'granted'`, then add the loader module to
CONSENT_GATED_ALLOWLIST below with a comment saying where the gate is. The point is a
recorded decision, not an absence of pixels forever.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# The surface a cold ad click lands on, plus the HTML shell every page is built from.
SCAN_DIRS = [
    REPO / "frontend" / "src" / "pages" / "public",
    REPO / "frontend" / "src" / "components" / "marketing",
    REPO / "frontend" / "public",
]
SCAN_FILES = [REPO / "frontend" / "index.html"]
SCAN_SUFFIXES = {".ts", ".tsx", ".js", ".jsx", ".html"}

# Modules that legitimately load a pixel BEHIND the consent gate. Empty by design — add an
# entry only together with the gate itself, and say in the comment where that gate lives.
CONSENT_GATED_ALLOWLIST: set[str] = set()

# This file must be able to name the things it forbids.
EXEMPT_NAMES = {"check_ad_pixel_consent.py"}
EXEMPT_PARTS = ("/__tests__/", "/node_modules/", "/dist/")

BANNED = [
    (re.compile(r"\bfbq\s*\(", re.I), "Meta pixel (`fbq`)"),
    (re.compile(r"connect\.facebook\.net", re.I), "Meta pixel loader (connect.facebook.net)"),
    (re.compile(r"\bgtag\s*\(\s*['\"]config['\"]\s*,\s*['\"]AW-", re.I), "Google Ads conversion tag"),
    (re.compile(r"googleadservices\.com|googlesyndication\.com", re.I), "Google Ads conversion script host"),
    (re.compile(r"\bttq\b\s*\.|analytics\.tiktok\.com", re.I), "TikTok pixel"),
    (re.compile(r"\blintrk\s*\(|snap\.licdn\.com", re.I), "LinkedIn Insight Tag"),
    (re.compile(r"\btwq\s*\(|static\.ads-twitter\.com", re.I), "X/Twitter pixel"),
    (re.compile(r"\bredditPixel\b|pixel\.redditmedia\.com", re.I), "Reddit pixel"),
    # OpenAI's ads product is the wave-two channel; its pixel is the same class of tag.
    (re.compile(r"openai[-_.]?(ads|pixel)|ads\.openai\.com", re.I), "OpenAI conversion pixel"),
]

# A banned token inside a comment is discussion, not a shipped tag.
_COMMENT_PREFIXES = ("*", "//", "/*", "<!--", "#")


def iter_files():
    paths = list(SCAN_FILES)
    for d in SCAN_DIRS:
        if d.exists():
            paths.extend(p for p in d.rglob("*") if p.suffix in SCAN_SUFFIXES)
    for path in paths:
        if not path.is_file():
            continue
        posix = path.as_posix()
        if path.name in EXEMPT_NAMES or any(part in posix for part in EXEMPT_PARTS):
            continue
        if path.relative_to(REPO).as_posix() in CONSENT_GATED_ALLOWLIST:
            continue
        yield path


def main() -> int:
    hits = []
    for path in iter_files():
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            if line.lstrip().startswith(_COMMENT_PREFIXES):
                continue
            for pattern, label in BANNED:
                if pattern.search(line):
                    hits.append((path.relative_to(REPO), lineno, line.strip()[:120], label))

    if not hits:
        print("[ad-pixel-consent] OK — no ungated third-party ad pixel on the public surface.")
        return 0

    print(f"[ad-pixel-consent] FAIL — {len(hits)} ungated ad pixel reference(s):\n")
    for rel, lineno, snippet, label in hits:
        print(f"  {rel}:{lineno}\n    {snippet}\n    ↳ {label}\n")
    print(
        "The ADS geography rule permits EU targeting only while no third-party ad pixel is\n"
        "installed (docs/gtm/ADS-5_otto_campaign_brief.md, Geography). A pixel is exactly the\n"
        "thing ePrivacy Art. 5(3) requires consent for.\n\n"
        "Either drop the pixel, or gate it behind the ConsentBanner and add the loader to\n"
        "CONSENT_GATED_ALLOWLIST in this script — with a comment saying where the gate is."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())

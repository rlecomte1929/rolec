#!/usr/bin/env bash
#
# check_ad_landing_prerender.sh — pre-launch gate for the paid-ad landing pages.
#
# WHY THIS EXISTS
# ---------------
# On 2026-08-10, hours before the first campaign, both ADS-3 landing pages were live and
# returned HTTP 200 — and served a 1,677-byte empty SPA shell to every crawler. The
# prerendered HTML existed, but only as a directory index: reachable at
# `/mobility-teams/` and invisible at `/mobility-teams`, which is the form every URL in
# ADS-4 used. An ad crawler does not run JS, so it would have validated a blank page, and
# the whole ADS-3 build would have bought nothing.
#
# HTTP 200 is not the check. Prerendered *content* is the check. That is what this
# asserts: the page must arrive with its own <title> and real markup inside #root,
# without executing a line of JavaScript.
#
# Run before every campaign launch, and after any change to prerender.mjs, the Render
# static-site routing, or the CDN in front of it.
#
# Usage:  bash scripts/check_ad_landing_prerender.sh [base_url]
# Exit:   0 = every page prerendered · 1 = at least one served the shell
set -uo pipefail

BASE="${1:-https://relopass.com}"

# path::expected string that only appears in the PRERENDERED markup, never in the shell.
# Sourced from frontend/src/pages/public/adLandingContent.ts via prerender-entry.tsx.
CHECKS=(
  "/mobility-teams/::Mobility teams · ReloPass"
  "/relocation-checklist/::Relocation checklist · ReloPass"
)

# The shell is small; a real prerendered page is several KB of markup. Anything under
# this is the shell even if the title somehow matched.
MIN_BYTES=5000

fail=0

for entry in "${CHECKS[@]}"; do
  path="${entry%%::*}"
  expect="${entry##*::}"
  url="${BASE}${path}"

  body="$(curl -sS --max-time 30 -A 'OAI-AdsBot/1.0 (+prerender-gate)' "$url" 2>/dev/null)"
  bytes=${#body}

  if [ "$bytes" -lt "$MIN_BYTES" ]; then
    echo "FAIL  $url — ${bytes} bytes, below the ${MIN_BYTES}-byte floor. This is the SPA shell."
    echo "      A crawler sees an empty page here. Do not launch against this URL."
    fail=1
    continue
  fi

  if ! printf '%s' "$body" | grep -qF "<title>${expect}</title>"; then
    echo "FAIL  $url — ${bytes} bytes but no <title>${expect}</title>."
    echo "      Served something, but not this page's prerendered HTML."
    fail=1
    continue
  fi

  echo "OK    $url — ${bytes} bytes, prerendered title present."
done

# The slash-less form is what a human types and what a backlink usually carries. It is
# allowed to be the shell — the ads do not use it — but say so plainly, because a reader
# of this output will assume the bare URL works.
for entry in "${CHECKS[@]}"; do
  path="${entry%%::*}"
  bare="${path%/}"
  bytes="$(curl -sS --max-time 30 -o /dev/null -w '%{size_download}' "${BASE}${bare}" 2>/dev/null || echo 0)"
  if [ "$bytes" -lt "$MIN_BYTES" ]; then
    echo "note  ${BASE}${bare} (no trailing slash) is still the shell — ${bytes} bytes."
    echo "      Expected until the _redirects rewrite is honoured. Ads must keep the slash."
  else
    echo "OK    ${BASE}${bare} (no trailing slash) now prerenders too — ${bytes} bytes."
  fi
done

if [ "$fail" -ne 0 ]; then
  echo
  echo "GATE FAILED — at least one ad landing page serves a blank document to crawlers."
  exit 1
fi

echo
echo "GATE PASSED — every ad destination serves prerendered HTML."

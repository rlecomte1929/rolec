#!/usr/bin/env bash
#
# check_public_prerender.sh — served-response gate for the 8 PUBLIC marketing routes.
#
# WHY THIS EXISTS, AND WHY IT IS NOT verify-prerender.mjs
# ------------------------------------------------------
# `frontend/scripts/verify-prerender.mjs` checks FILES ON DISK. That is necessary and it
# is not sufficient. On 2026-08-10 the ad landing pages' prerendered files were correct,
# the URLs returned HTTP 200, and production served a 1,677-byte empty shell to every
# crawler — because Render resolves `dist/<route>/index.html` as a directory index ONLY
# when the request carries a trailing slash. A build-time check cannot see that. This can.
#
# HTTP 200 is not the check. Prerendered content is the check.
#
# BOTH URL FORMS ARE ASSERTED HERE, and that is the difference from
# check_ad_landing_prerender.sh, which tolerates the slash-less form because the ad
# platform is handed the slash version. These are organic marketing URLs: humans type
# them, backlinks carry them, and sitemap/canonical tags use the bare form. A crawler
# hitting `/platform` and getting the shell is the whole failure mode, so a bare-form
# miss here is a FAIL, not a note.
#
# Run after any change to prerender-entry.tsx, prerender.mjs, or render.yaml's routes,
# and after every deploy that touches the frontend.
#
# Usage:  bash scripts/check_public_prerender.sh [base_url]
# Exit:   0 = every route prerendered in both forms · 1 = at least one served the shell
set -uo pipefail

BASE="${1:-https://relopass.com}"

# path::expected <title>. Titles come from each page's usePageMeta call; the build-time
# gate asserts the emitted files match those sources, so these stay in step.
CHECKS=(
  "/::ReloPass — Global mobility infrastructure"
  "/platform::The Platform · ReloPass"
  "/why::Why ReloPass"
  "/how-it-works::How It Works · ReloPass"
  "/get-started::Get started · ReloPass"
  "/security::Security · ReloPass"
  "/privacy::Privacy Policy · ReloPass"
  "/access::Get Started · ReloPass"
)

# The shell is 1,677 bytes. The smallest prerendered page here is ~9 kB. 5,000 leaves
# room for copy edits without letting the shell through.
MIN_BYTES=5000

# A real crawler UA, not a spoofed AI-crawler one. Spoofing OAI-SearchBot from a laptop
# or CI gets a correct 403 — Cloudflare verifies bots by signature/IP/rDNS, never by the
# UA string — so using one here would fail for reasons that have nothing to do with
# prerendering. See AIQ-1782.
UA='Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)'

fail=0
checked=0

check_one() {
  local url="$1" expect="$2" label="$3"
  local body bytes
  body="$(curl -sS --max-time 30 -A "$UA" "$url" 2>/dev/null)"
  bytes=${#body}
  checked=$((checked + 1))

  if [ "$bytes" -lt "$MIN_BYTES" ]; then
    echo "FAIL  $url ($label) — ${bytes} bytes, below the ${MIN_BYTES}-byte floor. This is the SPA shell."
    echo "      A crawler reads nothing here. If the file exists, the render.yaml rewrite is missing."
    fail=1
    return
  fi

  if ! printf '%s' "$body" | grep -qF "<title>${expect}</title>"; then
    echo "FAIL  $url ($label) — ${bytes} bytes but no <title>${expect}</title>."
    echo "      Served real markup, but not this route's page. Check for a rewrite pointing at the wrong file."
    fail=1
    return
  fi

  if printf '%s' "$body" | grep -qF 'Loading ReloPass'; then
    echo "WARN  $url ($label) — prerendered, but the loading splash is still present in the markup."
  fi

  echo "OK    $url ($label) — ${bytes} bytes, prerendered title present."
}

echo "check_public_prerender: ${BASE} — 8 routes, both URL forms"
echo

for entry in "${CHECKS[@]}"; do
  path="${entry%%::*}"
  expect="${entry##*::}"

  check_one "${BASE}${path}" "$expect" "bare"

  # `/` has no slash-less variant to test.
  if [ "$path" != "/" ]; then
    check_one "${BASE}${path}/" "$expect" "slash"
  fi
done

echo
if [ "$fail" -ne 0 ]; then
  echo "RESULT: FAIL — at least one route served the shell across ${checked} checks."
  echo
  echo "Most likely causes, in order:"
  echo "  1. render.yaml is missing a rewrite for that route, or it sits BELOW the /* catch-all"
  echo "     (routes are first-match-wins)."
  echo "  2. The deploy has not finished — Render serves the previous build until it flips."
  echo "  3. prerender-entry.tsx no longer lists the route, so no file was emitted."
  exit 1
fi

echo "RESULT: PASS — ${checked}/${checked} checks prerendered."

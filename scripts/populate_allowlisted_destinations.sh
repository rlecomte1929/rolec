#!/usr/bin/env bash
# ----------------------------------------------------------------------
# Populate the AI catalog for the seeded HR-allowlist destinations.
#
# What it does
#   1. Calls GET  /api/hr/catalog/scrape-quota and prints today's
#      remaining call budget.
#   2. Estimates total cost (destinations × categories) and warns +
#      asks for confirmation if the remaining quota looks insufficient.
#   3. POSTs /api/hr/catalog/populate-destination-with-ai once per
#      destination, printing the per-category breakdown returned by
#      the API.
#
# Pre-requisites
#   - The catalog_destination_allowlist seed has been applied
#     (supabase/seeds/catalog_destination_allowlist.sql). Without it,
#     each populate call returns {"status":"pending_admin_approval",...}
#     and opens a ticket instead of scraping.
#   - The backend env has OPENAI_API_KEY set; otherwise the per-category
#     responses come back as "scraper_disabled" (no quota charge).
#
# Auth — get a bearer token
#   The HR backend uses POST /api/auth/login (see
#   backend/app/routers/auth.py). Body: {"identifier","password"}.
#   The response includes `token`. Example:
#
#     curl -sS -X POST "$API/api/auth/login" \
#       -H "Content-Type: application/json" \
#       -d '{"identifier":"hr.demo@relopass.local","password":"Passw0rd!"}' \
#       | jq -r .token
#
#   Use any HR or ADMIN account. The token is a bearer; pass it as
#   $TOKEN below.
#
# Usage
#   API=https://api.example.com TOKEN=eyJ... ./scripts/populate_allowlisted_destinations.sh
#
#   Run for one destination only:
#     API=... TOKEN=... ./scripts/populate_allowlisted_destinations.sh \
#       --only "London|United Kingdom"
#
#   Skip the confirmation prompt (CI / non-interactive):
#     API=... TOKEN=... CONFIRM=yes ./scripts/populate_allowlisted_destinations.sh
#
# Expected output per destination
#   {
#     "status": "completed",
#     "destination_city": "London",
#     "country": "United Kingdom",
#     "categories_total": <N>,
#     "categories_populated": <P>,        ← actually scraped this run
#     "categories_skipped_existing": <S>, ← already had rows, no quota hit
#     "categories_quota_blocked": <Q>,    ← daily cap reached mid-loop
#     "total_inserted": <rows>,
#     "per_category": [{ "category": "...", "status": "...", "inserted": N }, ...],
#     "quota": { "day": "YYYY-MM-DD", "used": ..., "limit": 20, "remaining": ... }
#   }
#
#   If a destination is NOT yet on the allowlist:
#     { "status": "pending_admin_approval", "request": {...}, "message": "..." }
#
# No DB writes from this script — only HTTP calls to your API.
# ----------------------------------------------------------------------

set -euo pipefail

if [[ -z "${API:-}" || -z "${TOKEN:-}" ]]; then
  cat <<EOF >&2
error: set API and TOKEN env vars before running.
  API=https://api.example.com TOKEN=eyJ... $0
See the header of this script for how to obtain a token.
EOF
  exit 2
fi

# Default destination list — edit if you've seeded a different set.
DESTINATIONS=(
  "London|United Kingdom"
  "Singapore|Singapore"
  "Paris|France"
  "Frankfurt|Germany"
  "Amsterdam|Netherlands"
)

# --only "City|Country" overrides the list to a single pair.
if [[ "${1:-}" == "--only" && -n "${2:-}" ]]; then
  DESTINATIONS=("$2")
fi

require() {
  command -v "$1" >/dev/null 2>&1 || { echo "error: $1 is required" >&2; exit 2; }
}
require curl
require jq

auth=(-H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json")

echo "→ Checking quota at $API/api/hr/catalog/scrape-quota"
quota_json=$(curl -sS "${auth[@]}" "$API/api/hr/catalog/scrape-quota")
echo "  $quota_json"

remaining=$(echo "$quota_json" | jq -r '.remaining // 0')
limit=$(echo "$quota_json" | jq -r '.limit // 0')
day=$(echo "$quota_json" | jq -r '.day // "?"')

# Worst-case estimate: every destination scrapes every category.
# Categories is fetched indirectly — we don't have a public list endpoint
# in scope, so we use a conservative upper bound matching the registry
# size (Movers, Banks, Schools, Insurance, Electricity, Living Areas, ...).
# Adjust if your deployment has a different category count.
EST_CATEGORIES_PER_DEST=8
est_total=$(( ${#DESTINATIONS[@]} * EST_CATEGORIES_PER_DEST ))

echo "→ Today is $day; quota remaining = $remaining / $limit"
echo "→ Worst-case need = ${#DESTINATIONS[@]} destinations × ~$EST_CATEGORIES_PER_DEST categories = ~$est_total calls"
echo "  (Categories already populated short-circuit and do NOT charge quota,"
echo "   so actual cost is usually lower than the worst-case figure.)"
echo

if (( remaining < est_total )); then
  echo "⚠️  warning: remaining quota ($remaining) < worst-case estimate ($est_total)."
  echo "    Some categories may come back as \"quota_blocked\" — re-run tomorrow"
  echo "    after the midnight-UTC reset to finish them."
  if [[ "${CONFIRM:-}" != "yes" ]]; then
    read -r -p "Proceed anyway? [y/N] " ans
    case "$ans" in
      y|Y|yes|YES) ;;
      *) echo "aborted."; exit 0 ;;
    esac
  fi
fi

for pair in "${DESTINATIONS[@]}"; do
  city="${pair%%|*}"
  country="${pair#*|}"
  echo
  echo "→ Populating $city, $country"
  payload=$(jq -nc --arg c "$city" --arg co "$country" \
    '{destination_city:$c, country:$co}')
  curl -sS "${auth[@]}" -X POST \
    "$API/api/hr/catalog/populate-destination-with-ai" \
    -d "$payload" | jq '.'
done

echo
echo "→ Final quota state"
curl -sS "${auth[@]}" "$API/api/hr/catalog/scrape-quota" | jq '.'

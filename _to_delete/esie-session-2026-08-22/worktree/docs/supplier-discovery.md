# Supplier discovery — providers, cost, and how to enable

Discovery (`backend/app/services/maps_discovery.py`, admin "Discover" tab) sources real
businesses from a maps provider into the Supplier Registry as **pending** capabilities (they go
to `/admin/vetting-queue`, hidden from employees per the GAP 3 vetting filter until approved).

It is **provider-agnostic and off by default** — baseline cost is **$0** until you deliberately
enable a provider. Enable selectively against a concrete coverage gap, then turn it back off.

## Providers

| | **Apify** (`compass/crawler-google-places`) | **Google Places** (official Text Search) |
|---|---|---|
| Env | `DISCOVERY_PROVIDER=apify` + `APIFY_API_TOKEN` | `DISCOVERY_PROVIDER=google_places` + `GOOGLE_PLACES_API_KEY` |
| Data | name, **website**, phone, rating, reviews (one call) | name, address, rating, reviews — **no website/phone** (Text Search omits them) |
| Cost | per-run / per-place; **$5/mo free tier** | pay-per-request; Google monthly free credit |
| Dedup quality | strong (has website domain) | weaker (name only) |
| Notes | third-party scraper | official/reliable; we intentionally do **not** add a 2nd Place-Details call (would double cost) |

**Recommendation (pre-revenue):** start with **Apify** — its free tier likely covers selective
use (~$0), and one call returns websites (better dedup + supplier quality). Keep Google Places as
the alternate; the env-swap lets you A/B the same searches and standardize later. If you want
websites from Google Places, switch to Apify rather than paying for Place Details.

## Cost guardrails (always on)

- **Off by default** — no `DISCOVERY_PROVIDER` env → `disabled` → returns `[]`, no network, no cost.
- **Per-search result cap** — `DISCOVERY_MAX_RESULTS` (default **10**, clamped 1–60). Bounds the
  cost of a single search (esp. Apify, which bills per place).
- **Daily search quota** — reuses `catalog_scrape_quota` (`DEFAULT_DAILY_QUOTA=20`/day, keyed
  `admin-discovery`). `POST /discover` returns **429** past the limit. Quota is **only charged when
  a provider is actually configured** — poking the tab while off costs nothing.
- **Allowlist-gated** — `/discover` only fires for cities in `catalog_destination_allowlist`.
- The admin UI shows the active provider, remaining daily searches, and the per-search cap; the
  key itself is never returned by the API.

## Enable it (when targeting a gap)

1. Add the secret key via the **Render dashboard** (`APIFY_API_TOKEN` or `GOOGLE_PLACES_API_KEY`)
   — never paste it into a terminal/session that records to a git-tracked file.
2. Set `DISCOVERY_PROVIDER=apify` (or `google_places`); optionally tune `DISCOVERY_MAX_RESULTS`.
3. Manual Deploy on Render (env changes need a redeploy).
4. Verify `GET /api/admin/catalog/discovery-status` → `configured: true`.
5. Run a few targeted searches in the Discover tab, import the good ones (they land in the vetting
   queue), then **set `DISCOVERY_PROVIDER=disabled` again** to return to $0 baseline.

See also [supplier-systems-state.md](supplier-systems-state.md).

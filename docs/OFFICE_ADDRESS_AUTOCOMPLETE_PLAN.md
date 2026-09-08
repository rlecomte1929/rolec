# Office Address Autocomplete — Free Preliminary Solution + Pluggable Provider Architecture

Status: draft for review · Prepared: 2026-07-01
Trigger: beta feedback — "office address at destination" in the intake wizard's Work & Place
step is plain free text with no suggestions; requested Google Places or similar.

## Context

`office_address` (`EmployeeIntakePage.tsx`) is a bare text input today. AIQ-1345 added a
*debounced, after-the-fact* geocode check (`frontend/src/components/geocode.ts`) against the
free OpenStreetMap Nominatim API, purely to show a "Verified" / "Couldn't find that address"
badge and to feed the commute map — it does not suggest anything while the user types, and
Nominatim's own usage policy explicitly disallows using its public instance as an autocomplete
backend at any real volume. So the actual gap — guided suggestions while typing — is unbuilt,
and the existing geocoder isn't a legal substrate to build it on.

You have a Google Workspace account but not a Google Maps Platform / Google Cloud billing
account — those are separate products with separate billing, so Google Places isn't actually
free-to-turn-on today even though it feels like it should be. This plan ships a **$0, no-account**
solution now, built so that adding a paid provider later is an **admin config change, not a
re-build**.

## Goals

**Short-term (ship this sprint, zero cost, no external account needed):**
- Replace blind free-text entry with real-time address suggestions using a provider that
  permits autocomplete use for free, with no API key or billing account.
- Never make the field stricter than it is today — free text must always remain a valid
  fallback; step validity stays "non-empty string," not "must resolve to a real place."
- Build the provider as a swappable backend abstraction from day one, even though only one
  free provider is wired up initially, so upgrading later needs no frontend rework and no
  redeploy of the matching logic.

**Long-term (once a Google Cloud / Maps Platform billing account exists):**
- An admin can add a Google Places (or another paid provider's) API key from the Admin UI and
  flip the active provider for the whole platform without a code deploy.
- Session-token-based billing is correctly implemented for providers that require it (Google),
  so cost tracks actual searches, not keystrokes.
- Admins get basic usage/cost visibility for whichever provider is active, mirroring the
  existing AI-catalog-scrape quota pattern (`scrape_safety.py`) rather than inventing a new one.

**Explicit non-goals for this pass:** capturing lat/lng from the autocomplete provider and
retiring the existing Nominatim geocode step — the map pipeline stays untouched; a reusable
`AddressAutocompleteInput` for *other* address fields elsewhere in the app — build the component
generically, but only wire it into `office_address` now.

## Architecture

**Provider abstraction (backend).** A small interface, not a speculative plugin framework:

```
backend/app/services/geocoding_provider_base.py   — Protocol: autocomplete(), resolve()
backend/app/services/geocoding_provider_photon.py — free, no key, wired up now
backend/app/services/geocoding_provider_google.py — stubbed now, implemented when you have a key
backend/app/services/geocoding_service.py         — reads active-provider config, dispatches
```

`autocomplete(query, country_hint, session_token) -> list[Suggestion]` returns lightweight
`{label, ref, lat, lng}` results. Photon returns coordinates directly in the same response, so
for Photon `resolve()` is a no-op cache read. Google's flow needs a separate Place Details call
to get coordinates, so `resolve(ref, session_token) -> PlaceDetails` does real work only for
providers that need it. This keeps the frontend to **one code path** regardless of which
provider is active.

**Admin-configurable provider (the pluggable part).** One new table, `geocoding_provider_config`
— a singleton settings row, not a generic "integrations" system (no other integration needs this
today; building a general framework now would be exactly the kind of speculative complexity your
own CLAUDE.md guidelines warn against).

```sql
-- Illustrative — real migration follows the RLS hard gates (enable RLS, admin-only
-- policy, revoke anon) per CLAUDE.md.
CREATE TABLE public.geocoding_provider_config (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  provider         text NOT NULL DEFAULT 'photon' CHECK (provider IN ('photon','google_places','mapbox')),
  api_key_encrypted text,             -- NULL for photon; Fernet-encrypted at rest for paid providers
  enabled          boolean NOT NULL DEFAULT true,
  updated_by       uuid REFERENCES public.profiles(id),
  updated_at       timestamptz NOT NULL DEFAULT now()
);
```

The API key is encrypted with a backend-only symmetric key (new env var
`INTEGRATION_SECRETS_KEY`) before it's stored, and is **never** sent back to any frontend,
including the admin's own browser — the admin page shows a masked placeholder after saving, not
a decrypt-and-display round trip. This is the same posture as every other secret in this
codebase (`SUPABASE_SERVICE_ROLE_KEY`, `OPENAI_API_KEY`) — server-only, never shipped client-side.

**Backend endpoints:**
- `GET /api/geo/autocomplete?input=&sessionToken=` — employee-authenticated, resolves the active
  provider from config, returns suggestions.
- `GET /api/geo/resolve?ref=&sessionToken=` — resolves coordinates when the active provider
  needs a details step (Google); no-ops for Photon.
- Admin-only: `GET/PUT /api/admin/integrations/geocoding` (read current config minus the raw
  key; update provider + optionally rotate the key), `POST /api/admin/integrations/geocoding/test`
  (fires one real query server-side and reports pass/fail — lets an admin confirm a newly-pasted
  key actually works before employees start depending on it).
- Per CLAUDE.md's hard rule, every new router here gets registered in **both**
  `backend/main.py` and `backend/app/main.py`.

**Frontend:**
- `frontend/src/hooks/useAddressAutocomplete.ts` — debounced (~250ms), generates a
  `crypto.randomUUID()` session token on field focus, reuses it across keystrokes, retires it
  after a selection or on blur.
- `frontend/src/components/AddressAutocompleteInput.tsx` — new component, styled like the
  existing `CountryCombo`/`CityCombo` dropdown pattern already in `EmployeeIntakePage.tsx` so it
  looks native to the wizard rather than like an embedded third-party widget. Replaces the plain
  `Input` bound to `office_address`. Free typing without selecting a suggestion remains valid —
  the component never forces a selection.
- `frontend/src/pages/admin/AdminIntegrationsPage.tsx` (or a new tab on an existing admin
  settings page) — provider dropdown, conditionally-shown API key field (password-masked,
  write-only), Save, and a "Test connection" button.

## Rollout sequencing

1. **Phase 1 (this sprint, $0):** provider abstraction + `geocoding_provider_photon.py` +
   `/api/geo/*` endpoints + `AddressAutocompleteInput` wired into `office_address`. Ships with
   Photon as the hardcoded-default active provider — the `geocoding_provider_config` table can
   even be seeded with a single `provider='photon', enabled=true` row and the admin UI can wait
   until Phase 2 if you want the smallest possible first PR.
2. **Phase 2 (whenever you set up Maps Platform billing):** `geocoding_provider_google.py` +
   session-token-aware Place Details call + the admin settings page + key encryption. No changes
   needed to `AddressAutocompleteInput` or the intake wizard — the provider swap is invisible to
   the frontend by design.
3. **Phase 3 (optional, later):** reuse `AddressAutocompleteInput` on any other address field
   that turns out to need it; consider capturing lat/lng straight from the autocomplete provider
   to retire the redundant Nominatim geocode call.

## Metrics

**Short-term (Photon rollout) success metrics:**
- Share of `office_address` entries completed by picking a suggestion vs. typed free-text to
  the end (new lightweight event, e.g. `intake.office_address.autocomplete_selected` /
  `.manual_entry`, mirroring the `identity_event` instrumentation pattern already used
  elsewhere). Target: majority of new entries select a suggestion.
- Drop in the existing `officeGeo.status === 'notfound'` rate for new intake submissions,
  before vs. after rollout — a real suggestion should geocode successfully far more often than
  free text did.
- Guardrail: no increase in Work & Place step drop-off/abandonment — confirms the change didn't
  make the field feel more restrictive.
- Photon error/timeout rate — it's a best-effort public service; this tells you if/when self-
  hosting or moving up the Phase 2 timeline is warranted.

**Long-term (Phase 2) success metrics:**
- Google Cloud Console session count vs. raw autocomplete-request count stays close to 1:1 —
  direct proof the session-token implementation is actually saving money, not just present in
  code.
- An admin can swap the active provider and see it take effect with zero deploys — a
  capability metric, verified via the "Test connection" flow.

## Verification process

- **Manual QA, Phase 1:** type partial office addresses in each of the ~7 destination countries
  the platform currently has requirement content for (US, UK, Germany, France, Netherlands,
  Norway, Singapore); confirm suggestions appear and selecting one populates the field and still
  feeds the existing "Verified" badge / commute map correctly downstream.
- **Failure-mode QA:** point the frontend at a deliberately broken endpoint (or throttle
  network) and confirm the field still accepts manual free text and Continue is never blocked —
  this is the actual "avoid an error message and confusion" requirement from the original
  feedback, so it needs an explicit test, not just an assumption.
- **Automated tests:** unit tests for `geocoding_provider_photon.py` against a mocked Photon
  response; a unit test proving the stored API key round-trips through encryption without ever
  appearing in a serialized API response; an integration test hitting `/api/geo/autocomplete`
  against a stubbed provider.
- **Security checklist (both phases):** confirm the API key never appears in any network
  response reachable from the browser (manual network-tab check); confirm the new table's RLS —
  enabled, admin-only policy, anon revoked — per CLAUDE.md's hard migration gate; run
  `get_advisors` (Supabase MCP) after the migration; confirm both routers are registered per the
  dual-registration rule with the `python3 -c "from backend.main import app; ..."` check CLAUDE.md
  specifies.
- **Cost verification (Phase 2 only):** after enabling Google, watch Cloud Console billing for
  48 hours to confirm sessions track searches, not keystrokes, before trusting it at scale.
- **Rollback:** because the active provider is runtime DB config, "rollback" is an admin flipping
  the dropdown back to Photon (or disabling autocomplete entirely, which falls back to the plain
  text input that exists today) — no deploy required. Worth confirming this actually works as
  part of Phase 1 sign-off, since it's the whole point of building the abstraction now.

## Known limitations of the free tier (be upfront about these)

- Photon has no first-class "restrict to this country" parameter the way Google's
  `includedRegionCodes` does — only a location-bias center point — so suggestions for the
  destination country will be *weighted*, not strictly filtered. Google in Phase 2 will be
  noticeably more precise for edge-case destinations.
- Photon's public instance is best-effort with no uptime SLA. If it turns out to be flaky in
  practice, that's the trigger to prioritize Phase 2 rather than eating a QA cost on the free tier.
- Even though Photon needs no account or key, it's still a third party the office address text
  leaves the platform to — worth a line in `docs/security/PRIV-004_sub-processor_register.md`
  now rather than waiting for Phase 2, since your own CLAUDE.md calls for logging every
  sub-processor when it's added, not just the paid ones.

## Open questions for you

1. Ship Phase 1 with the admin settings table seeded but no admin UI yet (smallest first PR,
   provider swap still possible via a direct DB update until the UI exists), or build the admin
   page in the same PR even though there's nothing to plug in yet?
2. Any objection to Photon specifically, given the ToS/positioning differences from Nominatim
   (it's built for this use case, but it is still a Komoot-run public service)?

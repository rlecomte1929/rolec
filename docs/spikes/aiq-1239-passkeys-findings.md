# AIQ-1239 — Supabase Passkeys / WebAuthn Sign-In: Feasibility Findings

**Spike, read-only.** No auth or prod-config code was changed by this spike. Evidence is drawn
from the installed SDK in `frontend/node_modules/@supabase/auth-js@2.97.0`, the app's auth code,
and Supabase's June-2026 changelog.

## TL;DR / Verdict

The AIQ-1239 *"Sign in with Face ID button"* is **NOT achievable as scoped** (a one-tap,
from-scratch passwordless login) with the currently-installed SDK and the app's hybrid token
model. Two independent blockers:

1. **The installed SDK (`@supabase/supabase-js`/`auth-js` 2.97.0) exposes WebAuthn only as an
   MFA *second factor*** (`mfa.enroll/challenge/verify` with `factorType: 'webauthn'`). There is
   **no `signInWithPasskey()` / `registerPasskey()` / `signInWithWebAuthn()` top-level method.**
   A true passwordless first-touch login is not a single SDK call here.
2. **Even a successful passkey ceremony yields a Supabase session, not the ReloPass token the
   entire API depends on.** No "exchange Supabase session → ReloPass token" path exists; building
   it is net-new work that touches token issuance → **🔴 Red autonomy tier.**

A passkey *step-up / MFA factor for already-logged-in users* (Phase A below) **is** achievable
near-term and low-risk. The marketed one-tap passwordless button (Phase B) is a bigger, Red-tier
project.

---

## Q1 — Does Supabase expose passwordless passkey sign-in?

**Installed version:** `@supabase/supabase-js@^2.97.0` (resolved 2.97.0), bundling
`@supabase/auth-js@2.97.0` (`frontend/package.json`; `node_modules/@supabase/auth-js/package.json`).

**Top-level `signInWith*` methods present in `GoTrueClient.d.ts`:**
`signInWithPassword`, `signInWithOtp`, `signInWithOAuth`, `signInWithSSO`, `signInWithIdToken`,
`signInWithWeb3` (+ `signInWithSolana`, `signInWithEthereum` convenience aliases).
**There is no `signInWithPasskey`, `registerPasskey`, or `signInWithWebAuthn`.**

**WebAuthn IS present — but as an MFA factor only.** Evidence from
`node_modules/@supabase/auth-js/dist/module/lib/types.d.ts`:
- `FactorTypes = readonly ['totp','phone','webauthn']`
- `mfa.enroll(params: MFAEnrollWebauthnParams)` (line ~1000)
- `mfa.challenge(params: MFAChallengeWebauthnParams)` (line ~1008)
- `mfa.verify(params: MFAVerifyWebauthnParams)` (line ~1016)

There is also a client-side helper module `lib/webauthn.dom.ts` + `lib/webauthn.ts` (serialize /
deserialize `navigator.credentials.create()/.get()` options to/from base64url, plus a
`WebAuthnAbortService` singleton), all annotated **`@experimental`**.

**Changelog claim vs SDK reality:** the June-2026 developer update
(`https://supabase.com/changelog/46689-developer-update-june-2026`) markets *"Users can now sign
in with biometrics (Face ID, Touch ID, Windows Hello), a device PIN, or a hardware security key…
passwordless and phishing-resistant,"* **Beta**. But at the *installed-SDK* level WebAuthn is
wired through the MFA (AAL1 → AAL2) primitives, which require an **existing AAL1 session** to
challenge/verify. So:

> **Passwordless passkey sign-in (true first-touch): NOT a first-class method in 2.97.0.**
> **WebAuthn-as-2nd-factor (MFA / step-up): YES, fully present (Beta/experimental).**

These two are very different, and the AIQ assumes the former.

---

## Q2 — Fit with the app's HYBRID auth model

**Today's login flow** (`backend/app/routers/auth.py`):
`POST /api/auth/login` → PBKDF2 (`pbkdf2_sha256`) verify against `public.users` → mint a **ReloPass
UUID session token** via `db.create_session(token, user_id)` → **asynchronously** sync the user
into Supabase Auth (`supabase_auth_sync.sync_relopass_user_to_supabase_auth`, on a background
thread-pool) so `signInWithPassword`/RLS works later.

- **ReloPass token is PRIMARY.** `frontend/src/api/client.ts` reads `relopass_token` from storage
  and sends `Authorization: Bearer <relopass_token>` on every API call. The backend
  `get_current_user` (`backend/app/auth_deps.py`) validates that Bearer token as a ReloPass UUID
  session — **it does not accept a Supabase JWT.**
- **Supabase session is SECONDARY** — used only for RLS / realtime / document queries.

**The directions are opposite.** A passkey login produces a **Supabase session first and NO
ReloPass token** — exactly the reverse of today's "ReloPass-first, Supabase-synced-after" flow.
So after a passkey sign-in the app is effectively unauthenticated against its own API until a
ReloPass token is minted.

**Is there an existing exchange path? No.** The only place the backend touches a Supabase
access token is `POST /api/auth/logout`, which reads `supabase_access_token` from the body purely
to **revoke** it (`revoke_supabase_session`) — never to mint. Minting a ReloPass token from a
verified Supabase passkey session is **net-new**: a new endpoint (e.g. `POST /api/auth/exchange`)
that (a) verifies the Supabase JWT (admin `getUser` or JWKS), (b) resolves the `public.users` row
by email / auth UID, (c) calls `db.create_session(...)`. **That endpoint mints session tokens →
🔴 Red tier, full security review.**

---

## Q3 — Config toggle, device matrix, conflicts

**Config toggle:** `supabase/config.toml` lines 297–300 already contain the commented block:
```toml
# Configure MFA via WebAuthn
# [auth.mfa.web_authn]
# enroll_enabled = true
# verify_enabled = true
```
Uncommenting enables the **WebAuthn MFA factor** (`[auth.mfa]` is a **Pro-plan** feature;
`max_enrolled_factors = 10`; TOTP/phone currently disabled). This enables enroll/verify of a
webauthn *factor* — it does NOT, by itself, create a passwordless login button.

**Device matrix (WebAuthn platform authenticators):**

| Platform | Mechanism | Works |
|---|---|---|
| Safari / iOS, macOS | Face ID / Touch ID (iCloud Keychain passkeys) | Yes |
| Chrome / Android | Google Password Manager passkeys, fingerprint | Yes |
| Windows + Edge/Chrome | Windows Hello (PIN/face/fingerprint) | Yes |
| Any | Hardware security key (YubiKey etc.) | Yes |

Requires **HTTPS** and a correct **RP ID** (registrable domain). `localhost` is allowed for dev.

**Conflicts:** Passkeys are **additive** — they do **not** conflict with the existing Google
OAuth (`signInWithOAuth({provider:'google'})`) or email/password flows. The real friction is not a
conflict but the token-model gap in Q2.

**Enterprise-IT caveats:** some corporate MDM/browser policies block platform authenticators or
cross-device (hybrid/caBLE) passkeys; some orgs mandate security-key-only; RP ID must match the
production domain exactly; the feature is **Beta** (API may change); MFA requires Supabase **Pro**.

---

## Recommended follow-up plan

**Phase A — Passkey as MFA step-up for logged-in users (🟡 Yellow, near-term).**
- Enable `[auth.mfa.web_authn]` in **STAGING** config only.
- Add an "Add a passkey" action in Account/Security using `supabase.auth.mfa.enroll/challenge/
  verify({factorType:'webauthn'})` + the experimental `webauthn.dom` helpers.
- No ReloPass-token change (user already has a ReloPass session). Delivers biometric step-up and
  de-risks the WebAuthn ceremony/device matrix before the bigger build.
- Files: `frontend/src/features/.../security/*` (new); no backend auth change.

**Phase B — True "Sign in with Face ID" passwordless button (🔴 Red, the real AIQ-1239).**
- Net-new `POST /api/auth/exchange`: verify Supabase passkey JWT → resolve `public.users` →
  `db.create_session` → return a ReloPass token. **Touches token issuance → mandatory security
  review, Red tier.** Register the new router in **both** `backend/main.py` and
  `backend/app/main.py` (per CLAUDE.md dual-registration rule).
- Frontend "Sign in with Face ID" on `AuthScreen.tsx` driving the passkey ceremony, then calling
  `/api/auth/exchange` to obtain the ReloPass token the rest of the API needs.
- Re-evaluate the SDK: if a first-class `signInWithPasskey()` lands in a later `auth-js`, prefer
  upgrading over hand-rolling the discoverable-credential flow.
- Files: `backend/app/routers/auth.py`, `backend/main.py`, `backend/app/main.py`,
  `backend/app/auth_deps.py`, `frontend/src/features/platform-v2/auth/AuthScreen.tsx`,
  `frontend/src/api/client.ts`.

**Likely tier for AIQ-1239 as written: 🔴 Red** (it reaches ReloPass-token issuance).

### STAGING-only `config.toml` change (illustration — DO NOT apply to prod)
```diff
-# Configure MFA via WebAuthn
-# [auth.mfa.web_authn]
-# enroll_enabled = true
-# verify_enabled = true
+# Configure MFA via WebAuthn (STAGING ONLY — passkey spike AIQ-1239)
+[auth.mfa.web_authn]
+enroll_enabled = true
+verify_enabled = true
```

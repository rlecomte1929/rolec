# Keeping the backend warm (AIQ-1014 / PERF-3, infra lever)

The backend `rolec-eu` (`srv-d7ku…`) runs on the Render **`free` plan**, which
spins the instance down after ~15 min of inactivity. The next request pays a full
app cold-start — this is the **7.7s** the 2026-06-13 perf audit observed (warm
steady-state is sub-3s; see `authed_audit_2026-06.md`). Keeping the instance warm
eliminates that cold-start **without a billing change** (the user's chosen lever
over a plan upgrade).

## Why the existing GitHub Actions pinger is not enough

`.github/workflows/keepalive.yml` pings `/health` on a `*/12` schedule. Two gaps
made it ineffective in practice:

1. **GitHub throttles high-frequency scheduled workflows — hard.** The cron asks
   for a run every 12 min, but the actual run history fires only **a handful of
   times per day**, with **3–5 hour gaps** (e.g. 2026-06-16: 11:27 → 16:11 UTC,
   a ~4.7h gap). In those gaps the free instance idles out (>15 min) and
   cold-starts. GitHub explicitly does not guarantee scheduled-run timing and
   deprioritises frequent crons, so this cannot be fixed from the workflow side.
2. **It was Mon-Fri only.** Weekends were fully uncovered. **2026-06-13 (the audit
   date) was a Saturday** — a guaranteed cold-start. *(Fixed: the schedule now
   runs all 7 days; nights still accept the cold start.)*

Net: the Actions cron is a **best-effort supplement**, not a dependable keep-warm.
Tightening it further is self-defeating — if GitHub *did* honour `*/12` 7×13h it
would blow past the 2000 free Actions minutes/month, and if it throttles (as it
does) it's too sparse to work.

## The reliable, free fix — an external uptime monitor

Use a purpose-built pinger that is **not** subject to GitHub's cron throttling and
costs **no** Actions minutes. Recommended: **[cron-job.org](https://cron-job.org)**
(free, no friction) or **[UptimeRobot](https://uptimerobot.com)** (free tier, 5-min
checks). One-time human setup (≈2 min):

1. Create a free account.
2. Add a cron job / monitor:
   - **URL:** `https://api.relopass.com/health`
   - **Method:** `GET`
   - **Interval:** every **5 minutes**, **24/7** (well inside the ~15-min spin-down).
   - **Expected:** HTTP `200`.
3. (Optional) enable failure alerts to your email — doubles as uptime monitoring.

That alone keeps the instance warm around the clock and eliminates the cold-start
the audit flagged, with zero billing and zero Actions minutes.

## Alternative — upgrade the Render plan (paid, zero-maintenance)

Moving `rolec-eu` off `free` to a Starter+ plan removes spin-down entirely, so no
pinger is needed and there is no cold-start ever. This is the cleanest fix but is a
**billing decision** — deliberately left to a human, not changed autonomously.
(Note: a prior queue task claimed to have done this "plan upgrade", but the service
is still on `free` — verify before assuming it's handled.)

## Recommendation

- **Now (free):** set up the cron-job.org / UptimeRobot monitor above. Reliable,
  24/7, no cost. Treat `keepalive.yml` as a redundant best-effort backup.
- **Later (when revenue/launch justifies it):** upgrade the Render plan and retire
  both pingers.

The warm-path N+1 fixes (`/api/employee/policy/caps`, `/api/hr/policy-config/published`)
are a separate, code-side PERF-3 lever — see `authed_audit_2026-06.md`.

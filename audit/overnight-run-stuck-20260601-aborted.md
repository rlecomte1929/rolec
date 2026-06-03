# Overnight run — stuck / blocked log

Append-only. Each entry: what blocked, evidence, next human action, main SHA at time of attempt.

---

## 2026-06-01 00:04 CEST — RUN-WIDE BLOCKER (not a single PR): GitHub Actions billing block

**Severity:** Hard stop. Run aborted before any merge. 0 PRs merged, 0 PRs closed.

**Failure mode:** CI cannot run at all. Every GitHub Actions job — across every workflow and every branch — fails to *start* with:

> "The job was not started because recent account payments have failed or your spending limit needs to be increased. Please check the 'Billing & plans' section in your settings"

**Evidence:**
- Last `[CI]` run on `main` (run `26695300417`, head `90b84e1`, the #211 merge commit): all 5 jobs `failure`, all with the billing annotation. Verified jobs: Backend tests P1 (`78678700008`), HR Dashboard build (`78678700011`), Actionlint (`78678700013`), Frontend build (`78678700020`).
- Every `[Render keepalive]` cron run since 2026-05-30 21:24 UTC also fails to start with the identical billing annotation.
- No successful Actions run exists on any branch since 2026-05-30 21:24 UTC.

**Why this stops the whole run (per `audit/overnight-run-plan.md`):**
- Plan "Hard rules" → CI gating: "Do not merge any PR with a failing CI check unless the failure is identified as a pre-existing main flake." A billing outage is NOT a flake; it is a hard block, and it affects every PR.
- Plan "Hard rules": "Never merge if main is currently broken." Main's last CI is red.
- Every block step requires "wait for CI green" and `gh pr checks/run watch` — impossible while Actions is billing-blocked.
- Render auto-deploys on push to `main` via its own GitHub webhook (independent of Actions billing), so merging now would ship unverified code straight to the live prod deploy with no CI gate and no deploy-watch — the exact compounding-risk scenario the plan's hard stops guard against.

**Not the cause:** production is healthy. `GET https://api.relopass.com/health` → `HTTP 200` (`{"status":"ok","version":"1.0.0"}`). The red CI is purely the billing block, not a code regression on main.

**Next human action (morning):**
1. Fix GitHub billing: GitHub → Settings → Billing & plans → resolve failed payment / raise spending limit for the `rlecomte1929` account.
2. Re-run the last `main` CI (`gh run rerun 26695300417`) and confirm it goes green — this validates main is actually healthy, not just billing-blocked.
3. Once Actions is confirmed working and main CI is green, re-launch this overnight run from Block 1 (#179). No state was changed, so it restarts cleanly.

**Main SHA at time of attempt:** `90b84e12762496b2337f69e96417d7af1a4e3f2d`

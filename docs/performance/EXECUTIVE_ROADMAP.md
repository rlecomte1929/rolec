# ReloPass Performance Executive Roadmap

This roadmap is designed for a non-specialist audience. It focuses on the improvements most likely to make the product feel faster and reduce avoidable engineering cost.

## Current Readout

- Backend startup is still the clearest high-ROI target. A local import-time run shows `backend.main` reaching about `861 ms` before it hits import-time database writes.
- Relocation-plan assembly is not currently the biggest compute risk. A synthetic full-plan benchmark averages about `0.34 ms`, which suggests any real slowness is more likely in DB reads or request wiring than in the plan builder itself.
- Frontend admin lazy loading is in place, but the app still imports `43` non-admin page modules eagerly.
- Policy upload processing now runs in the background, but there is not yet a measured throughput baseline from analytics data.
- Admin scaling risk is real but likely incremental, not urgent fire-fighting. The company index still mixes orphan scans and correlated subqueries in one read path.

## Priority Order

| Priority | Area | Benefit | Effort | ROI | Why it matters |
| --- | --- | --- | --- | --- | --- |
| 1 | Backend startup and import-time work | High | Medium | Very high | Faster cold starts help every deploy, restart, and first request. |
| 2 | Relocation-plan end-to-end request timing | Medium-high | Low | High | The code path is fast in isolation, so a short timing audit can quickly reveal the real bottleneck. |
| 3 | Frontend loading cost on key screens | Medium | Low-medium | High | Lighter pages improve perceived quality quickly, especially for HR users on slower devices. |
| 4 | Admin query hotspots and scaling risk | Medium | Low-medium | Medium-high | Small query and index fixes now are cheaper than a larger admin rewrite later. |
| 5 | Policy-document throughput and failure visibility | Medium | Low | Medium | Upload UX is faster, but we still need real completion and failure data before investing further. |

## Recommended Next Actions

### 1. Reduce backend startup work

- Move database initialization and other write-like setup out of module import.
- Break up the heaviest imports in `backend/main.py`.
- Keep import-time profiling as a repeatable audit so this does not regress.

Expected outcome: faster cold starts, safer deploys, and less time lost to backend boot friction.

### 2. Measure the relocation-plan request end to end

- Add span timings around the main reads feeding `/api/relocation-plans/{case_id}/view`.
- Compare cached versus uncached requests before deciding on snapshotting.
- Treat snapshot/materialized-view work as a second step only if measurements justify it.

Expected outcome: faster improvement with less guesswork.

### 3. Continue trimming frontend initial load

- Audit the top three business-critical non-admin routes first.
- Lazy-load the heaviest remaining routes that are not part of the first screen.
- Use the existing frontend perf helpers to compare before and after.

Expected outcome: pages feel quicker without needing a major redesign.

### 4. Fix admin query hotspots in small steps

- Start with the company index and review queue paths.
- Add a measured query-plan pass in staging or production.
- Apply small index and aggregation fixes before considering structural rewrites.

Expected outcome: better admin scalability with low implementation risk.

### 5. Measure policy throughput before adding more infrastructure

- Use `analytics_events` in staging or production to measure upload-to-classification completion.
- Group failures by cause so fixes target the highest-value document issues.
- Only introduce a dedicated job queue if real throughput or reliability data shows background tasks are not enough.

Expected outcome: better HR reliability without over-engineering.

## Deliverable Format

For each audit area, keep the output in the same simple structure:

- Current baseline
- Why it is slow
- Fix options
- Effort estimate
- Benefit estimate
- Recommended priority
- Plain-language business outcome

That keeps the roadmap decision-friendly for non-specialists and implementation-friendly for engineers.

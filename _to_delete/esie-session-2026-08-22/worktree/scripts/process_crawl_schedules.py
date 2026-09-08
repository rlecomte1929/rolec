#!/usr/bin/env python3
"""
Process due crawl schedules. Run from cron or manually:

  python scripts/process_crawl_schedules.py

Calls the scheduler service to process all due schedules.
Requires DATABASE_URL and Supabase env vars for DB access.
"""
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("process_crawl_schedules")


def main() -> int:
    from backend.app.services.crawl_scheduler_service import (
        process_due_schedules,
        sync_tier_schedules,
    )

    # Self-heal the per-tier cron schedules (daily / weekly / monthly) before
    # processing due runs, so the tier config (AIQ-689 / P2-02a) is always live.
    tier_sync = sync_tier_schedules(user_id=None)
    log.info("Synced %d tier schedules: %s", len(tier_sync), tier_sync)

    results = process_due_schedules(user_id=None)
    log.info("Processed %d schedules: %s", len(results), results)
    failed = [r for r in results if r.get("status") == "failed"]
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

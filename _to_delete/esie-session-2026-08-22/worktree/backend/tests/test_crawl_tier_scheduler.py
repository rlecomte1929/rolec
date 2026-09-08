"""
Tests for per-tier crawl scheduling (AIQ-689 / P2-02a).

Covers the tier config (cadence + cron + trust_tier mapping), the next-run
timing produced by the per-tier cron expressions, and the idempotent
sync_tier_schedules() entry point (Supabase mocked).
"""
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


class TestTierConfig(unittest.TestCase):
    def test_three_tiers_with_expected_cadence(self):
        from backend.app.services.crawl_tier_config import (
            TIER_1_CRITICAL,
            TIER_1_STABLE,
            TIER_2,
            TIER_CONFIGS,
        )

        self.assertEqual(TIER_CONFIGS[TIER_1_CRITICAL].cadence_days, 1)
        self.assertEqual(TIER_CONFIGS[TIER_1_STABLE].cadence_days, 7)
        self.assertEqual(TIER_CONFIGS[TIER_2].cadence_days, 30)

    def test_trust_tier_mapping(self):
        from backend.app.services.crawl_tier_config import (
            TIER_1_CRITICAL,
            TIER_1_STABLE,
            TIER_2,
            tier_for_trust_tier,
        )

        self.assertEqual(tier_for_trust_tier("T0"), TIER_1_CRITICAL)
        self.assertEqual(tier_for_trust_tier("t1"), TIER_1_STABLE)
        self.assertEqual(tier_for_trust_tier("T2"), TIER_2)
        self.assertEqual(tier_for_trust_tier("T3"), TIER_2)

    def test_unknown_trust_tier_falls_back_to_tier_2(self):
        from backend.app.services.crawl_tier_config import TIER_2, tier_for_trust_tier

        self.assertEqual(tier_for_trust_tier(None), TIER_2)
        self.assertEqual(tier_for_trust_tier("garbage"), TIER_2)


class TestTierCronTiming(unittest.TestCase):
    """The per-tier cron expressions must produce daily / weekly / monthly runs."""

    def test_tier_1_critical_is_daily(self):
        from backend.app.services.crawl_scheduler_service import _compute_next_run
        from backend.app.services.crawl_tier_config import TIER_CONFIGS, TIER_1_CRITICAL

        cfg = TIER_CONFIGS[TIER_1_CRITICAL]
        start = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        first = _compute_next_run("cron", cfg.cron_expression, from_time=start)
        second = _compute_next_run("cron", cfg.cron_expression, from_time=first)
        self.assertEqual((second - first).days, 1)
        self.assertEqual(first.hour, 2)

    def test_tier_1_stable_is_weekly(self):
        from backend.app.services.crawl_scheduler_service import _compute_next_run
        from backend.app.services.crawl_tier_config import TIER_CONFIGS, TIER_1_STABLE

        cfg = TIER_CONFIGS[TIER_1_STABLE]
        start = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        first = _compute_next_run("cron", cfg.cron_expression, from_time=start)
        second = _compute_next_run("cron", cfg.cron_expression, from_time=first)
        self.assertEqual((second - first).days, 7)
        self.assertEqual(first.weekday(), 0)  # Monday

    def test_tier_2_is_monthly(self):
        from backend.app.services.crawl_scheduler_service import _compute_next_run
        from backend.app.services.crawl_tier_config import TIER_2, TIER_CONFIGS

        cfg = TIER_CONFIGS[TIER_2]
        start = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        first = _compute_next_run("cron", cfg.cron_expression, from_time=start)
        second = _compute_next_run("cron", cfg.cron_expression, from_time=first)
        self.assertEqual(first.day, 1)
        self.assertEqual(second.day, 1)
        # Next monthly run lands in the following month.
        self.assertNotEqual(first.month, second.month)

    def test_seven_day_window_no_missed_critical_runs(self):
        """Over a 7-day window the daily tier yields exactly 7 distinct run days."""
        from backend.app.services.crawl_scheduler_service import _compute_next_run
        from backend.app.services.crawl_tier_config import TIER_1_CRITICAL, TIER_CONFIGS

        cfg = TIER_CONFIGS[TIER_1_CRITICAL]
        cursor = datetime(2026, 6, 1, 0, 0, 0, tzinfo=timezone.utc)
        run_days = set()
        for _ in range(7):
            cursor = _compute_next_run("cron", cfg.cron_expression, from_time=cursor)
            run_days.add(cursor.date())
        self.assertEqual(len(run_days), 7)


class TestSyncTierSchedules(unittest.TestCase):
    def _mock_supabase(self, existing_by_name=None):
        existing_by_name = existing_by_name or {}
        supabase = MagicMock()

        def table(_name):
            tbl = MagicMock()

            # select(...).eq("name", X).limit(1).execute()
            def select(*_a, **_k):
                sel = MagicMock()

                def eq(col, val):
                    res = MagicMock()
                    res.limit.return_value.execute.return_value.data = (
                        [existing_by_name[val]] if val in existing_by_name else []
                    )
                    return res

                sel.eq.side_effect = eq
                return sel

            tbl.select.side_effect = select
            tbl.insert.return_value.execute.return_value.data = [{"id": "new-id"}]
            tbl.update.return_value.eq.return_value.execute.return_value.data = [{}]
            return tbl

        supabase.table.side_effect = table
        return supabase

    def test_creates_all_three_tiers_when_none_exist(self):
        import backend.app.services.crawl_scheduler_service as svc

        supabase = self._mock_supabase(existing_by_name={})
        with patch.object(svc, "_get_supabase", return_value=supabase):
            results = svc.sync_tier_schedules()

        self.assertEqual(len(results), 3)
        self.assertTrue(all(r["action"] == "created" for r in results))
        tiers = {r["tier"] for r in results}
        self.assertEqual(tiers, {"tier-1-critical", "tier-1-stable", "tier-2"})

    def test_unchanged_when_already_in_sync(self):
        import backend.app.services.crawl_scheduler_service as svc
        from backend.app.services.crawl_tier_config import (
            TIER_CONFIGS,
            TIER_ORDER,
            schedule_name_for_tier,
        )

        existing = {}
        for tier in TIER_ORDER:
            cfg = TIER_CONFIGS[tier]
            existing[schedule_name_for_tier(tier)] = {
                "id": f"id-{tier}",
                "schedule_expression": cfg.cron_expression,
                "crawl_tier": tier,
                "schedule_type": "cron",
            }
        supabase = self._mock_supabase(existing_by_name=existing)
        with patch.object(svc, "_get_supabase", return_value=supabase):
            results = svc.sync_tier_schedules()

        self.assertTrue(all(r["action"] == "unchanged" for r in results))

    def test_repairs_drifted_cron_expression(self):
        import backend.app.services.crawl_scheduler_service as svc
        from backend.app.services.crawl_tier_config import (
            TIER_ORDER,
            schedule_name_for_tier,
        )

        existing = {}
        for tier in TIER_ORDER:
            existing[schedule_name_for_tier(tier)] = {
                "id": f"id-{tier}",
                "schedule_expression": "0 0 * * *",  # wrong / drifted
                "crawl_tier": tier,
                "schedule_type": "cron",
            }
        supabase = self._mock_supabase(existing_by_name=existing)
        with patch.object(svc, "_get_supabase", return_value=supabase):
            results = svc.sync_tier_schedules()

        self.assertTrue(all(r["action"] == "updated" for r in results))


if __name__ == "__main__":
    unittest.main()

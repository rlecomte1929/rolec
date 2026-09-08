#!/bin/bash
# Run this script to push commits to GitHub.
# Render will auto-deploy from main.
# Contains:
#   0c21797 — destination request workflow + VT1/T13 test fixes
#   0d9db87 — AIQ-279 Employee wizard Steps 3-5 endpoints (WZ3/WZ4/WZ5)
#             + case_messages Supabase migration
#   b0e126f — AIQ-261-A CaseDraftDTO services field (WZ2 fix)
#   0ba86c7 — AIQ-261-B EmployeeIntakePage submit wired to PATCH /api/cases/{id}
#   51bb4db — AIQ-261-C BudgetSummaryPanel in Review step (WZ3)
#   1ea7cd1 — AIQ-261-D QuoteRequestPanel in My Needs step (WZ4)
#   eae6578 — AIQ-261-E CaseMessagesPanel in Review step (WZ5)
#   29c694d — AIQ-347 HUMAN-7E crisis-templates.ts (5 brand-voice templates)
#   372688d — AIQ-344 HUMAN-7B pre-call brief generator Edge Function
#             + 20260524120000_pre_call_brief_cron.sql migration
#   2ecb8b2 — AIQ-325 BRAIN-3E monthly Company Brain auto-update pipeline
#             + 20260524140000_brain_update.sql migration
#   4648944 — checkpoint: FOUNDATION-1B/1D analytics pipeline, PRODUCT-6 A/B testing,
#             SUPPORT-4 pipeline, DEV-LOOP-2C/2E autofix+digest, all remote-stub migrations,
#             lib/support-*.ts, lib/bug-classifier.ts, .github/workflows/autofix-ci.yml
set -e
cd "$(dirname "$0")"
rm -f .git/index.lock .git/HEAD.lock .git/packed-refs.lock 2>/dev/null || true
echo "Commits to push:"
git log --oneline origin/main..HEAD
echo ""
git -c http.proxy="" -c https.proxy="" push origin main
echo ""
echo "Pushed! Render will deploy in ~2 min."
echo ""
echo "Next: apply Supabase migrations (run from project root):"
echo "  supabase db push"
echo ""
echo "Migrations to apply:"
echo "  20260524110000_case_messages.sql"
echo "  20260524120000_pre_call_brief_cron.sql"
echo "  20260524140000_brain_update.sql"
echo "  20260524000001_analytics_events_and_daily_summaries.sql"
echo "  20260524000002_matching_5a_assignment_outcomes_and_supplier_stats.sql"
echo "  20260524000003_autofix_pipeline_cron.sql"
echo "  20260524000004_morning_digest_cron.sql"
echo "  20260524000005_support_tickets.sql"
echo "  20260524000006_support_triage_trigger.sql"
echo "  20260524000007_weekly_support_digest_cron.sql"
echo "  20260523010000_nightly_aggregation_cron.sql"
echo "  20260523020000_friction_analysis_summary_type.sql"
echo "  20260523020000_support_drafts.sql"
echo ""
echo "Next: deploy Edge Functions:"
echo "  supabase functions deploy capture-event"
echo "  supabase functions deploy nightly-aggregation"
echo "  supabase functions deploy pre-call-brief"
echo "  supabase functions deploy brain-update"
echo "  supabase functions deploy support-triage"
echo "  supabase functions deploy support-router"
echo "  supabase functions deploy support-reply"
echo "  supabase functions deploy weekly-support-digest"
echo "  supabase functions deploy autofix-pipeline"
echo "  supabase functions deploy morning-digest"
echo "  supabase functions deploy get-feature-flags"
echo "  supabase functions deploy friction-analysis"
echo ""
echo "Required Supabase vault env vars (set via dashboard → Settings → Vault):"
echo "  GOOGLE_CALENDAR_TOKEN  — for pre-call-brief"
echo "  ANTHROPIC_API_KEY      — for pre-call-brief, brain-update, support-reply, morning-digest"
echo "  NOTION_TOKEN           — for pre-call-brief, brain-update, morning-digest"
echo "  BRAIN_PAGE_ID          — optional, defaults to AIQ-324 page"
echo ""
echo "Then run the E2E suite to verify:"
echo "  node relopass_api_runner_patched.js"

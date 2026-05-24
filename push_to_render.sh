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
set -e
cd "$(dirname "$0")"
rm -f .git/index.lock .git/HEAD.lock .git/packed-refs.lock 2>/dev/null || true
echo "Commits to push:"
git log --oneline origin/main..HEAD
echo ""
git -c http.proxy="" -c https.proxy="" push origin main
echo ""
echo "Pushed! Render will deploy in ~2 min. Then apply the Supabase migration:"
echo "  supabase db push  (or apply via Supabase dashboard)"
echo ""
echo "Then run the E2E suite to verify improvements:"
echo "  node relopass_api_runner_patched.js"

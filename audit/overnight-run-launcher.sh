#!/bin/bash
# Overnight PR merge run launcher
# Kicks off Claude Code in autonomous mode at 2026-06-01 00:01 local time.
# Keeps the Mac awake from now until the run completes.
#
# Usage (run before going to bed, from any directory):
#   bash /Users/romainlecomte/Documents/GitHub/rolec/audit/overnight-run-launcher.sh
#
# The script will:
#   1. caffeinate the Mac (no sleep, no display sleep, no idle sleep)
#   2. sleep until 2026-06-01 00:01:00 local time
#   3. cd into the repo
#   4. launch `claude --dangerously-skip-permissions` with the overnight prompt
#   5. tee everything to a timestamped log under audit/
#   6. post a macOS notification when the run finishes
#
# To stop: Ctrl-C in the terminal where this is running, or `pkill -f overnight-run`.

set -uo pipefail

REPO="/Users/romainlecomte/Documents/GitHub/rolec"
PROMPT="${REPO}/audit/overnight-run-prompt.md"
TARGET="2026-06-01 00:01:00"

if [ ! -f "$PROMPT" ]; then
  echo "ERROR: prompt file not found at $PROMPT" >&2
  exit 1
fi

if ! command -v claude >/dev/null 2>&1; then
  echo "ERROR: \`claude\` CLI not on PATH. Install Claude Code first." >&2
  exit 1
fi

if ! command -v gh >/dev/null 2>&1; then
  echo "ERROR: \`gh\` CLI not on PATH. Install GitHub CLI first." >&2
  exit 1
fi

# Verify gh is authenticated
if ! gh auth status >/dev/null 2>&1; then
  echo "ERROR: \`gh\` is not authenticated. Run \`gh auth login\` first." >&2
  exit 1
fi

TARGET_EPOCH=$(date -j -f "%Y-%m-%d %H:%M:%S" "$TARGET" +%s 2>/dev/null)
if [ -z "$TARGET_EPOCH" ]; then
  echo "ERROR: could not parse target time \"$TARGET\"" >&2
  exit 1
fi

NOW_EPOCH=$(date +%s)
SLEEP_SECONDS=$((TARGET_EPOCH - NOW_EPOCH))

if [ "$SLEEP_SECONDS" -lt 0 ]; then
  echo "Target time $TARGET is in the past. Starting immediately."
  SLEEP_SECONDS=0
else
  HUMAN_DURATION=$(printf '%dh%dm' $((SLEEP_SECONDS/3600)) $((SLEEP_SECONDS%3600/60)))
  echo "Will start at $TARGET local time."
  echo "Sleeping for $HUMAN_DURATION ($SLEEP_SECONDS seconds)..."
  echo "Mac will be kept awake by caffeinate the entire time."
  echo "Leave this terminal window open. You can close the laptop lid only if it's plugged in."
fi

# Wrap the whole thing in caffeinate so the Mac stays awake from now through end of run.
# -d: prevent display sleep
# -i: prevent idle sleep
# -s: prevent system sleep on AC power
# -u: assert "user is active" (also keeps display on)
exec caffeinate -disu bash -c "
  set -uo pipefail

  if [ $SLEEP_SECONDS -gt 0 ]; then
    sleep $SLEEP_SECONDS
  fi

  cd '$REPO' || exit 1

  TIMESTAMP=\$(date +%Y%m%d-%H%M%S)
  LOGFILE='audit/overnight-run-'\$TIMESTAMP'.log'

  echo '=== Overnight run started at '\$(date)' ===' | tee \"\$LOGFILE\"
  echo 'Repo: $REPO' | tee -a \"\$LOGFILE\"
  echo 'Prompt: $PROMPT' | tee -a \"\$LOGFILE\"
  echo 'gh auth: '\$(gh auth status 2>&1 | head -3 | tail -1) | tee -a \"\$LOGFILE\"
  echo 'main HEAD: '\$(git rev-parse --short main) | tee -a \"\$LOGFILE\"
  echo '' | tee -a \"\$LOGFILE\"

  claude --dangerously-skip-permissions < '$PROMPT' 2>&1 | tee -a \"\$LOGFILE\"
  EXIT_CODE=\${PIPESTATUS[0]}

  echo '' | tee -a \"\$LOGFILE\"
  echo '=== Overnight run ended at '\$(date)' (exit '\$EXIT_CODE') ===' | tee -a \"\$LOGFILE\"

  osascript -e \"display notification \\\"Overnight run complete. Exit \$EXIT_CODE. Log: \$LOGFILE\\\" with title \\\"ReloPass overnight\\\" sound name \\\"Glass\\\"\" 2>/dev/null || true

  exit \$EXIT_CODE
"

#!/usr/bin/env bash
# Parker Framework Audit Pipeline — orchestrator
#
# Usage:
#   ./pipeline.sh init [--launched-externally A]
#   ./pipeline.sh status
#   ./pipeline.sh prompt <step>           # print + copy wrapped prompt for <step>
#   ./pipeline.sh verify <step>           # run tests, type-check, git diff
#   ./pipeline.sh complete <step>         # mark step done, advance pointer
#   ./pipeline.sh next                    # verify + complete current, show next prompt
#   ./pipeline.sh reset                   # wipe STATE.json (asks for confirmation)
#   ./pipeline.sh help
#
# Requirements: bash >= 4, jq, git. macOS pbcopy auto-detected for clipboard.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$ROOT/../.." && pwd)"
STATE_FILE="$ROOT/STATE.json"
RUNS_DIR="$ROOT/runs"
PROMPTS_DIR="$ROOT/prompts"
LIB_DIR="$ROOT/lib"
PREAMBLE_TMPL="$LIB_DIR/preamble.md.tmpl"
CLOSEOUT_TMPL="$LIB_DIR/closeout.md.tmpl"

STEPS=(A B C D E F G H I J)

step_slug() {
  case "$1" in
    A) echo "cox-survival" ;;
    B) echo "benefit-optimizer" ;;
    C) echo "cluster-tiering" ;;
    D) echo "prompt-registry" ;;
    E) echo "rlhf-lite" ;;
    F) echo "passport-ocr-oss" ;;
    G) echo "carbon-tco" ;;
    H) echo "conjoint" ;;
    I) echo "translation" ;;
    J) echo "nlg-variety" ;;
    *) return 1 ;;
  esac
}

step_title() {
  case "$1" in
    A) echo "Cox survival model for case timelines" ;;
    B) echo "Benefit-mix portfolio optimizer (Markowitz-style)" ;;
    C) echo "Cluster-relative supplier tiering" ;;
    D) echo "Prompt registry + canary A/B" ;;
    E) echo "RLHF-lite preference dataset from Notion Human Review" ;;
    F) echo "Open-source fallback for passport OCR" ;;
    G) echo "Carbon + per-customer AI unit economics" ;;
    H) echo "Conjoint analysis on benefit preferences" ;;
    I) echo "Neural translation layer (DeepL Pro + NLLB-200)" ;;
    J) echo "NLG variety (data-to-text, frame-based, extractive)" ;;
    *) return 1 ;;
  esac
}

# Per-step dependencies (which prior steps' RESULT.md must be consulted).
step_deps() {
  case "$1" in
    A|B|C|D|G|H|J) echo "" ;;
    E) echo "D" ;;
    F) echo "D" ;;
    I) echo "D G" ;;
    *) return 1 ;;
  esac
}

# ------------------------ utilities ------------------------

require() {
  command -v "$1" >/dev/null 2>&1 || { echo "ERROR: '$1' is required. Install it and retry." >&2; exit 1; }
}

require_init() {
  [ -f "$STATE_FILE" ] || { echo "ERROR: pipeline not initialized. Run './pipeline.sh init' first." >&2; exit 1; }
}

require_step() {
  local s="$1"
  case " ${STEPS[*]} " in *" $s "*) ;; *) echo "ERROR: '$s' is not a valid step. One of: ${STEPS[*]}" >&2; exit 1 ;; esac
}

run_id() { jq -r .run_id "$STATE_FILE"; }
current_step() { jq -r .current_step "$STATE_FILE"; }
step_status() { jq -r ".steps.\"$1\".status" "$STATE_FILE"; }
base_sha() { jq -r .base_sha "$STATE_FILE"; }

# Atomic state update — tempfile in the same directory as STATE.json so the
# `mv` is a same-filesystem rename (and therefore atomic). Using `mktemp` with
# /tmp breaks on bind-mounted workspaces.
_state_tempfile() {
  mktemp "$STATE_FILE.tmp.XXXXXX"
}

set_step_status() {
  local s="$1" status="$2"
  local tmp
  tmp="$(_state_tempfile)"
  jq ".steps.\"$s\".status = \"$status\" | .steps.\"$s\".updated_at = \"$(date -Iseconds)\"" "$STATE_FILE" > "$tmp"
  mv "$tmp" "$STATE_FILE"
}

set_current_step() {
  local s="$1"
  local tmp
  tmp="$(_state_tempfile)"
  jq ".current_step = \"$s\"" "$STATE_FILE" > "$tmp"
  mv "$tmp" "$STATE_FILE"
}

advance_current_step() {
  local cur next idx
  cur="$(current_step)"
  next=""
  local found=0
  for s in "${STEPS[@]}"; do
    if [ $found -eq 1 ]; then next="$s"; break; fi
    if [ "$s" = "$cur" ]; then found=1; fi
  done
  if [ -z "$next" ]; then
    set_current_step "DONE"
    echo "Pipeline complete. No further steps."
  else
    set_current_step "$next"
    echo "Current step advanced to: $next"
  fi
}

step_dir() {
  echo "$RUNS_DIR/$(run_id)/$1"
}

color() {
  local c="$1"; shift
  case "$c" in
    red)    printf '\033[31m%s\033[0m' "$*" ;;
    green)  printf '\033[32m%s\033[0m' "$*" ;;
    yellow) printf '\033[33m%s\033[0m' "$*" ;;
    blue)   printf '\033[34m%s\033[0m' "$*" ;;
    bold)   printf '\033[1m%s\033[0m'  "$*" ;;
    *)      printf '%s' "$*" ;;
  esac
}

# ------------------------ commands ------------------------

cmd_init() {
  require jq
  require git
  if [ -f "$STATE_FILE" ]; then
    echo "STATE.json already exists at $STATE_FILE"
    echo "Run './pipeline.sh reset' first if you want to start a new run."
    exit 1
  fi

  local launched_externally=""
  while [ $# -gt 0 ]; do
    case "$1" in
      --launched-externally) launched_externally="$2"; shift 2 ;;
      *) echo "Unknown flag: $1"; exit 1 ;;
    esac
  done

  local rid="run-$(date +%Y%m%d-%H%M%S)"
  local sha
  sha="$(cd "$REPO_ROOT" && git rev-parse HEAD)"

  mkdir -p "$RUNS_DIR/$rid"
  for s in "${STEPS[@]}"; do mkdir -p "$RUNS_DIR/$rid/$s"; done

  # Build step map
  local steps_json="{"
  local first=1
  for s in "${STEPS[@]}"; do
    local status="pending"
    if [ "$s" = "$launched_externally" ]; then status="in_progress"; fi
    if [ $first -eq 0 ]; then steps_json+=","; fi
    steps_json+="\"$s\":{\"status\":\"$status\",\"slug\":\"$(step_slug "$s")\",\"title\":\"$(step_title "$s")\"}"
    first=0
  done
  steps_json+="}"

  local current="${launched_externally:-A}"

  jq -n \
    --arg rid "$rid" \
    --arg sha "$sha" \
    --arg cur "$current" \
    --arg now "$(date -Iseconds)" \
    --argjson steps "$steps_json" \
    '{run_id:$rid, started_at:$now, base_sha:$sha, current_step:$cur, steps:$steps}' \
    > "$STATE_FILE"

  echo "$(color green '✓') Initialized run $(color bold "$rid")"
  echo "  Base SHA: $sha"
  echo "  Current step: $current"
  if [ -n "$launched_externally" ]; then
    echo "  Step $launched_externally marked as in_progress (launched externally)"
  fi
  echo
  echo "Next: run './pipeline.sh status' to see the board."
}

cmd_status() {
  require_init
  echo
  echo "$(color bold "Parker Framework Audit Pipeline")"
  echo "Run: $(color blue "$(run_id)")  |  Base SHA: $(base_sha)  |  Current: $(color yellow "$(current_step)")"
  echo
  printf "  %-3s  %-12s  %-50s  %s\n" "Step" "Status" "Title" "Slug"
  printf "  %-3s  %-12s  %-50s  %s\n" "----" "------" "-----" "----"
  for s in "${STEPS[@]}"; do
    local st sl tl marker color_name
    st="$(step_status "$s")"
    sl="$(step_slug "$s")"
    tl="$(step_title "$s")"
    marker=" "
    color_name="reset"
    case "$st" in
      completed) color_name="green";  marker="✓" ;;
      in_progress) color_name="yellow"; marker="…" ;;
      blocked) color_name="red"; marker="!" ;;
      pending) color_name="reset"; marker=" " ;;
    esac
    printf "  %s %-2s  %s  %-50s  %s\n" \
      "$(color "$color_name" "$marker")" \
      "$s" \
      "$(color "$color_name" "$(printf '%-12s' "$st")")" \
      "$tl" \
      "$sl"
  done
  echo
}

cmd_prompt() {
  require_init
  local s="${1:-}"
  [ -n "$s" ] || { echo "Usage: ./pipeline.sh prompt <step>" >&2; exit 1; }
  require_step "$s"

  local cur status
  cur="$(current_step)"
  status="$(step_status "$s")"

  if [ "$s" != "$cur" ]; then
    echo "$(color yellow "warning"): step $s is not the current step (current = $cur)."
    echo "Continuing anyway; this is useful when re-printing a prompt mid-run."
    echo
  fi

  local title slug deps
  title="$(step_title "$s")"
  slug="$(step_slug "$s")"
  deps="$(step_deps "$s")"

  # Build PREREQUISITES.md
  local dir
  dir="$(step_dir "$s")"
  mkdir -p "$dir"
  {
    echo "# Prerequisites for step $s — $title"
    echo
    if [ -z "$deps" ]; then
      echo "_No upstream dependencies. This step is independent._"
    else
      echo "Before implementing, read these RESULT.md files written by earlier steps."
      echo "Your code MUST align with what was ACTUALLY built in those steps, not what"
      echo "was sketched in the original audit prompt."
      echo
      for d in $deps; do
        local ddir
        ddir="$(step_dir "$d")"
        echo "- \`audit/parker-pipeline/runs/$(run_id)/$d/RESULT.md\` — step $d ($(step_title "$d"))"
        if [ -f "$ddir/RESULT.md" ]; then
          echo "  - Status: present, $(wc -l < "$ddir/RESULT.md" | tr -d ' ') lines"
        else
          echo "  - Status: $(color red 'MISSING'). Cannot proceed until step $d ships its RESULT.md."
        fi
      done
    fi
  } > "$dir/PREREQUISITES.md"

  # Wrapped prompt = preamble + body + closeout
  local out
  out="$(
    sed -e "s|<STEP>|$s|g" \
        -e "s|<TITLE>|$title|g" \
        -e "s|<SLUG>|$slug|g" \
        -e "s|<RUN_ID>|$(run_id)|g" \
        -e "s|<BASE_SHA>|$(base_sha)|g" \
        "$PREAMBLE_TMPL"
    echo
    echo "---"
    echo
    cat "$PROMPTS_DIR/$s-$slug.md"
    echo
    echo "---"
    echo
    sed -e "s|<STEP>|$s|g" \
        -e "s|<TITLE>|$title|g" \
        -e "s|<SLUG>|$slug|g" \
        -e "s|<RUN_ID>|$(run_id)|g" \
        -e "s|<BASE_SHA>|$(base_sha)|g" \
        "$CLOSEOUT_TMPL"
  )"

  # Save to disk
  printf '%s\n' "$out" > "$dir/PROMPT.md"

  # Print + copy to clipboard if available
  printf '%s\n' "$out"

  if command -v pbcopy >/dev/null 2>&1; then
    printf '%s' "$out" | pbcopy
    echo
    echo "$(color green '✓') Prompt also copied to clipboard ($(wc -c <<< "$out") bytes)."
  fi

  # Mark step as in_progress
  if [ "$status" = "pending" ]; then
    set_step_status "$s" "in_progress"
    echo "$(color green '✓') Step $s marked as in_progress."
  fi
  echo
  echo "Saved to: $(color blue "audit/parker-pipeline/runs/$(run_id)/$s/PROMPT.md")"
  echo
  echo "Next:"
  echo "  1. Paste the prompt into Claude Code (it should already be in your clipboard)."
  echo "  2. When Claude Code finishes, run: $(color bold "./pipeline.sh verify $s")"
  echo "  3. Review the verification, then: $(color bold "./pipeline.sh complete $s")"
}

cmd_verify() {
  require_init
  local s="${1:-}"
  [ -n "$s" ] || { echo "Usage: ./pipeline.sh verify <step>" >&2; exit 1; }
  require_step "$s"

  local dir
  dir="$(step_dir "$s")"
  mkdir -p "$dir"
  local out="$dir/VERIFICATION.md"
  local slug
  slug="$(step_slug "$s")"
  local branch_expected="audit/parker-step-$s-$slug"

  echo "Running verification for step $s..." >&2

  {
    echo "# Verification — step $s ($(step_title "$s"))"
    echo
    echo "_Generated: $(date -Iseconds)_"
    echo

    echo "## Git state"
    echo
    local current_branch
    current_branch="$(cd "$REPO_ROOT" && git rev-parse --abbrev-ref HEAD)"
    echo "- Current branch: \`$current_branch\`"
    echo "- Expected branch: \`$branch_expected\`"
    if [ "$current_branch" = "$branch_expected" ]; then
      echo "- Branch check: ✓ on expected branch"
    else
      echo "- Branch check: ⚠ on a different branch (this is OK if step opened a PR and you've already switched away)"
    fi
    echo
    echo "### Diff stats vs base"
    echo '```'
    (cd "$REPO_ROOT" && git diff "$(base_sha)...HEAD" --stat 2>&1 | tail -60) || true
    echo '```'
    echo

    echo "## Migrations"
    echo
    echo '```'
    (cd "$REPO_ROOT" && git diff "$(base_sha)...HEAD" --name-only -- 'supabase/migrations/**' 2>&1) || true
    echo '```'
    echo

    echo "## Backend tests (pytest)"
    echo
    echo '```'
    (cd "$REPO_ROOT/backend" && pytest -q 2>&1 | tail -80) || echo "[pytest failed or not run]"
    echo '```'
    echo

    echo "## Frontend type-check (tsc --noEmit)"
    echo
    echo '```'
    (cd "$REPO_ROOT/frontend" && npx tsc --noEmit 2>&1 | tail -50) || echo "[tsc failed or not run]"
    echo '```'
    echo

    echo "## RESULT.md presence"
    echo
    if [ -f "$dir/RESULT.md" ]; then
      echo "- ✓ RESULT.md exists ($(wc -l < "$dir/RESULT.md" | tr -d ' ') lines)"
    else
      echo "- ✗ RESULT.md is MISSING. Step is not finished — Claude Code must write it before completion."
    fi
    echo
    if [ -f "$dir/BLOCKED.md" ]; then
      echo "## ⚠ BLOCKED.md present"
      echo
      echo "Step reported a blocker. Read:"
      echo
      echo "    audit/parker-pipeline/runs/$(run_id)/$s/BLOCKED.md"
      echo
    fi
  } > "$out"

  echo "$(color green '✓') Verification written to $out"
  echo
  echo "Open it to review:"
  echo "  cat $out"
  echo
  echo "When you're satisfied, run: $(color bold "./pipeline.sh complete $s")"
}

cmd_complete() {
  require_init
  local s="${1:-}"
  [ -n "$s" ] || { echo "Usage: ./pipeline.sh complete <step>" >&2; exit 1; }
  require_step "$s"

  local dir
  dir="$(step_dir "$s")"

  if [ ! -f "$dir/RESULT.md" ]; then
    echo "$(color red 'ERROR'): $dir/RESULT.md is missing." >&2
    echo "Claude Code must write RESULT.md before this step can be marked complete." >&2
    exit 1
  fi
  if [ ! -f "$dir/VERIFICATION.md" ]; then
    echo "$(color yellow 'warning'): VERIFICATION.md missing — running verify first."
    cmd_verify "$s"
  fi

  set_step_status "$s" "completed"
  echo "$(color green '✓') Step $s marked as completed."

  if [ "$s" = "$(current_step)" ]; then
    advance_current_step
  fi

  local next
  next="$(current_step)"
  if [ "$next" = "DONE" ]; then
    echo "$(color green '✓✓✓') Pipeline complete. All 10 steps done."
  else
    echo
    echo "Next step: $next — $(step_title "$next")"
    echo "Run: $(color bold "./pipeline.sh prompt $next")"
  fi
}

cmd_next() {
  require_init
  local cur
  cur="$(current_step)"
  if [ "$cur" = "DONE" ]; then
    echo "Pipeline is already complete."
    exit 0
  fi
  echo "Verifying current step ($cur)..."
  cmd_verify "$cur"
  echo
  read -r -p "Mark step $cur as complete and show the next prompt? [y/N] " ans
  if [ "$ans" != "y" ] && [ "$ans" != "Y" ]; then
    echo "Aborted. No state change."
    exit 0
  fi
  cmd_complete "$cur"
  local next
  next="$(current_step)"
  if [ "$next" != "DONE" ]; then
    echo
    cmd_prompt "$next"
  fi
}

cmd_reset() {
  if [ ! -f "$STATE_FILE" ]; then
    echo "Nothing to reset."
    exit 0
  fi
  read -r -p "Delete STATE.json and all run artifacts under runs/? [y/N] " ans
  if [ "$ans" != "y" ] && [ "$ans" != "Y" ]; then
    echo "Aborted."
    exit 0
  fi
  rm -f "$STATE_FILE"
  rm -rf "$RUNS_DIR"
  echo "$(color green '✓') Pipeline reset."
}

cmd_help() {
  cat <<EOF
Parker Framework Audit Pipeline

Commands:
  init [--launched-externally <step>]  Bootstrap a new run.
  status                               Show pipeline board.
  prompt <step>                        Print + clipboard the wrapped prompt for <step>.
  verify <step>                        Run tests, type-check, write VERIFICATION.md.
  complete <step>                      Mark step done, advance current_step.
  next                                 verify + complete current step + print next prompt.
  reset                                Wipe STATE.json and runs/ (asks for confirmation).
  help                                 Show this help.

Files:
  STATE.json                           Pipeline state.
  runs/<run_id>/<step>/PROMPT.md       Wrapped prompt for the step.
  runs/<run_id>/<step>/PREREQUISITES.md  Auto-generated dep list.
  runs/<run_id>/<step>/PLAN.md         Written by Claude Code before coding.
  runs/<run_id>/<step>/RESULT.md       Written by Claude Code at closeout.
  runs/<run_id>/<step>/VERIFICATION.md Written by 'verify' command.
  runs/<run_id>/<step>/BLOCKED.md      Written by Claude Code if blocker found.

Step list:
EOF
  for s in "${STEPS[@]}"; do
    printf "  %s  %s\n" "$s" "$(step_title "$s")"
  done
}

# ------------------------ dispatch ------------------------

case "${1:-help}" in
  init)     shift; cmd_init "$@" ;;
  status)   cmd_status ;;
  prompt)   shift; cmd_prompt "$@" ;;
  verify)   shift; cmd_verify "$@" ;;
  complete) shift; cmd_complete "$@" ;;
  next)     cmd_next ;;
  reset)    cmd_reset ;;
  help|--help|-h) cmd_help ;;
  *) echo "Unknown command: $1"; cmd_help; exit 1 ;;
esac

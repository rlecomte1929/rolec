#!/usr/bin/env bash
# install-gstack.sh
# Installs Gstack skills to ~/.claude/skills/gstack/ for use with Claude Code CLI.
# Run once from your terminal: bash scripts/install-gstack.sh
set -e

SKILLS_DIR="$HOME/.claude/skills"
GSTACK_DIR="$SKILLS_DIR/gstack"

echo "Installing Gstack to $GSTACK_DIR ..."

mkdir -p "$SKILLS_DIR"

# Clone or update
if [ -d "$GSTACK_DIR/.git" ]; then
  echo "Already installed — pulling latest..."
  git -C "$GSTACK_DIR" pull --ff-only
else
  git clone https://github.com/rlecomte1929/gstack.git "$GSTACK_DIR"
fi

# Register skills: create real dirs in ~/.claude/skills/ with SKILL.md symlinks
# so Claude Code discovers them as top-level skills (not nested under gstack/)
echo "Registering skills..."
for skill_dir in "$GSTACK_DIR"/*/; do
  if [ -f "$skill_dir/SKILL.md" ]; then
    skill_name=$(grep -m1 '^name:' "$skill_dir/SKILL.md" 2>/dev/null \
      | sed 's/^name:[[:space:]]*//' | tr -d '[:space:]')
    [ -z "$skill_name" ] && skill_name="$(basename "$skill_dir")"
    target="$SKILLS_DIR/$skill_name"
    mkdir -p "$target"
    [ -L "$target/SKILL.md" ] && rm "$target/SKILL.md"
    ln -snf "$skill_dir/SKILL.md" "$target/SKILL.md"
    echo "  /$skill_name"
  fi
done

# Optional: build browse binary (for /qa, /design-review visual features)
# Requires bun — skip if not installed. /office-hours works without it.
if command -v bun >/dev/null 2>&1; then
  echo ""
  echo "bun found — building browse binary (enables visual features in /qa, /design-review)..."
  cd "$GSTACK_DIR"
  bun install --frozen-lockfile 2>/dev/null || bun install
  bun run build
  echo "Browse binary built."
else
  echo ""
  echo "Note: bun not installed — skipping browse binary build."
  echo "Core skills (/office-hours, /ship, /review, /investigate, etc.) work without it."
  echo "To enable visual features later: install bun (https://bun.sh) then run:"
  echo "  cd $GSTACK_DIR && bun install && bun run build"
fi

echo ""
echo "✓ Gstack installed. Open a new Claude Code session in your repo and type /office-hours"

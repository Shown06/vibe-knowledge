#!/usr/bin/env bash
# Vibe Knowledge — Installer
# Version: v1.1.0 (https://github.com/Shown06/vibe-knowledge/releases/tag/v1.1.0)
#
# This script is meant to be fetched from a pinned release tag, not from
# `main` — a tag is immutable, so the code you're about to run is exactly
# what shipped in the release above and won't silently change later:
#   bash <(curl -fsSL https://raw.githubusercontent.com/Shown06/vibe-knowledge/refs/tags/v1.1.0/install.sh)
# See all releases: https://github.com/Shown06/vibe-knowledge/releases
#
# Copies scripts to ~/.claude (stable, survives Google Drive eviction)
# Sets up data directory and registers hooks in settings.json
# Optionally registers the MCP server with Claude Code
set -euo pipefail

SRC="$(cd "$(dirname "$0")" && pwd)"
HOOK_DST="$HOME/.claude/hooks/vibe-knowledge"
DATA="$HOME/.claude/vibe-knowledge/data"
RUN="$HOME/.claude/vibe-knowledge/run"
SETTINGS="$HOME/.claude/settings.json"

echo "[1/5] Copying scripts to stable location: $HOOK_DST"
mkdir -p "$HOOK_DST" "$DATA" "$RUN"
cp "$SRC/hooks/capture.py"          "$HOOK_DST/capture.py"
cp "$SRC/hooks/build_card.py"       "$HOOK_DST/build_card.py"
cp "$SRC/hooks/distill.sh"          "$HOOK_DST/distill.sh"
cp "$SRC/hooks/distill-worker.sh"   "$HOOK_DST/distill-worker.sh"
# VIEW/BACKUP のパスをこのマシンの SRC に合わせて書き換える(OSS利用者対応)
python3 - "$HOOK_DST/distill-worker.sh" "$SRC" <<'PY'
import sys, re
dst, src = sys.argv[1], sys.argv[2]
with open(dst, encoding="utf-8") as f:
    txt = f.read()
txt = re.sub(r'^VIEW="[^"]*"', f'VIEW="{src}/view"', txt, flags=re.MULTILINE)
txt = re.sub(r'^BACKUP="[^"]*"', f'BACKUP="{src}/data-backup"', txt, flags=re.MULTILINE)
with open(dst, "w", encoding="utf-8") as f:
    f.write(txt)
print(f"  VIEW  -> {src}/view")
print(f"  BACKUP-> {src}/data-backup")
PY
chmod +x "$HOOK_DST"/*.py "$HOOK_DST"/*.sh

echo "[2/5] Data directory: $DATA"
touch "$DATA/events.jsonl"
[ -f "$DATA/.cursor" ] || echo 0 > "$DATA/.cursor"

CONFIG="$HOME/.claude/vibe-knowledge/config.json"
if [ ! -f "$CONFIG" ]; then
  cat > "$CONFIG" <<'JSON'
{
  "exclude_paths": [],
  "use_api_key": false
}
JSON
  echo "  + config.json created: $CONFIG"
else
  echo "  = config.json already exists (left untouched)"
fi
echo "  Tip: to stop capturing a specific project (e.g. client/NDA work), add a"
echo "       substring of its path to exclude_paths in config.json."
echo ""
echo "  [重要] このツールは今後、Claude Codeでの作業ごとに、あなたのClaude Pro/Max"
echo "  サブスクリプション枠を使って裏でカード生成を行います(既定動作)。"
echo "  This runs in the background on every Claude Code turn using your Claude"
echo "  Pro/Max subscription quota by default. To use metered API billing instead,"
echo "  set use_api_key to true in config.json and export ANTHROPIC_API_KEY."

echo "[3/5] Registering hooks in settings.json (idempotent)"
SKIP_HOOKS=0
echo ""
echo "  This step will modify: $SETTINGS"
echo "  It will add two hooks (only if not already present):"
echo "    - PostToolUse: runs capture.py after Edit/Write/MultiEdit/Bash"
echo "                   (logs what changed to ~/.claude/vibe-knowledge/data — no network calls)"
echo "    - Stop:        runs distill.sh when a Claude Code session ends"
echo "                   (turns the log into flashcards via a local haiku call)"
echo "  Your current settings.json will be backed up first, to:"
echo "    $SETTINGS.bak-vk-<timestamp>"
echo ""
if [ -t 0 ]; then
  read -r -p "  Proceed with registering these hooks? [y/N] " REPLY
  case "$REPLY" in
    [yY]|[yY][eE][sS]) : ;;
    *)
      SKIP_HOOKS=1
      echo "  Skipped. Vibe Knowledge is installed but will NOT capture sessions yet."
      echo "  To enable it later, either re-run this installer and answer 'y',"
      echo "  or manually add to $SETTINGS:"
      echo '    "hooks": {'
      echo '      "PostToolUse": [{"matcher": "Edit|Write|MultiEdit|Bash",'
      echo '                       "hooks": [{"type": "command", "command": "~/.claude/hooks/vibe-knowledge/capture.py", "timeout": 5}]}],'
      echo '      "Stop": [{"hooks": [{"type": "command", "command": "~/.claude/hooks/vibe-knowledge/distill.sh", "timeout": 8}]}]'
      echo '    }'
      ;;
  esac
else
  echo "  (non-interactive shell detected — proceeding without prompt, as before)"
fi

if [ "$SKIP_HOOKS" -eq 0 ]; then
  cp "$SETTINGS" "$SETTINGS.bak-vk-$(date '+%Y%m%d%H%M%S')"
  python3 - "$SETTINGS" <<'PY'
import json, sys
p = sys.argv[1]
with open(p, encoding="utf-8") as f:
    s = json.load(f)
h = s.setdefault("hooks", {})

cap_cmd = "~/.claude/hooks/vibe-knowledge/capture.py"
post = h.setdefault("PostToolUse", [])
if not any(cap_cmd in json.dumps(o, ensure_ascii=False) for o in post):
    post.append({"matcher": "Edit|Write|MultiEdit|Bash",
                 "hooks": [{"type": "command", "command": cap_cmd, "timeout": 5}]})
    print("  + PostToolUse(capture) 登録")
else:
    print("  = PostToolUse(capture) 既に登録済み")

dis_cmd = "~/.claude/hooks/vibe-knowledge/distill.sh"
stop = h.setdefault("Stop", [])
if not any(dis_cmd in json.dumps(o, ensure_ascii=False) for o in stop):
    stop.append({"hooks": [{"type": "command", "command": dis_cmd, "timeout": 8}]})
    print("  + Stop(distill) 登録")
else:
    print("  = Stop(distill) 既に登録済み")

with open(p, "w", encoding="utf-8") as f:
    json.dump(s, f, ensure_ascii=False, indent=2)
PY
fi

echo "[4/5] Validating settings.json"
python3 -c "import json;json.load(open('$SETTINGS'));print('  settings.json OK')"

echo "[5/5] MCP server setup (optional)"
MCP_SERVER="$SRC/mcp-server"
if [ -d "$MCP_SERVER" ]; then
  if [ ! -d "$MCP_SERVER/node_modules" ]; then
    echo "  Building MCP server..."
    (cd "$MCP_SERVER" && npm install --silent && npm run build --silent)
  fi
  MCP_BIN="$MCP_SERVER/dist/index.js"
  if command -v claude &>/dev/null; then
    if claude mcp list 2>/dev/null | grep -q "vibe-knowledge"; then
      echo "  = MCP server already registered"
    else
      claude mcp add vibe-knowledge node "$MCP_BIN"
      echo "  + MCP server registered: vibe-knowledge"
    fi
  else
    echo "  (claude CLI not found — register manually:)"
    echo "    claude mcp add vibe-knowledge node $MCP_BIN"
  fi
else
  echo "  (mcp-server directory not found — skipping)"
fi

echo ""
echo "Done. Start building with Claude Code — cards accumulate automatically."
echo "View your cards:  open $SRC/view/index.html"
echo "MCP in Claude:    try asking 'search my vibe knowledge for webhook'"

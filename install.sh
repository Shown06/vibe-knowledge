#!/usr/bin/env bash
# Vibe Knowledge — Installer
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

echo "[3/5] Registering hooks in settings.json (idempotent)"
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

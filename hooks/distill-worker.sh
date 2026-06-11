#!/usr/bin/env bash
# Vibe Knowledge - 翻訳ワーカー(本処理)
# 未処理の実装イベントを読み、claude -p(haiku)で中1向けカードに翻訳して蓄積する。
# サブスク内で動かすため ANTHROPIC_API_KEY を必ず外す。
set -uo pipefail
export VK_DISTILLING=1   # この配下で動く capture/distill を黙らせる(自己再帰防止)

VK_HOME="$HOME/.claude/vibe-knowledge"
DATA="$VK_HOME/data"
RUNDIR="$VK_HOME/run"
HOOKS="$HOME/.claude/hooks/vibe-knowledge"
# 閲覧UIの正本(Google Drive上)。退避中で書けない時は build_card 側が黙ってskip。
VIEW="/Users/two-de-sir/マイドライブ/株式会社ReFlow/GPT/vibe-knowledge/view"
# 大元データのGoogle Driveバックアップ先(大元はローカル維持・ここへコピーが同期される)
BACKUP="/Users/two-de-sir/マイドライブ/株式会社ReFlow/GPT/vibe-knowledge/data-backup"

EVENTS="$DATA/events.jsonl"
CURSOR="$DATA/.cursor"
LOCK="$DATA/.lock"
LOG="$DATA/distill.log"
MODEL="claude-haiku-4-5-20251001"

PY=$(command -v python3 || echo /usr/local/bin/python3)
CLAUDE=$(command -v claude || echo "$HOME/.local/bin/claude")

[ -f "$EVENTS" ] || exit 0

# --- 排他ロック(10分以上前の残骸は破棄して復帰) ---
if [ -d "$LOCK" ] && [ -n "$(find "$LOCK" -maxdepth 0 -mmin +10 2>/dev/null)" ]; then
  rmdir "$LOCK" 2>/dev/null || true
fi
mkdir "$LOCK" 2>/dev/null || exit 0
trap 'rmdir "$LOCK" 2>/dev/null || true' EXIT

# --- 未処理スライス(行カーソル方式) ---
N=$(wc -l < "$EVENTS" | tr -d ' ')
C=$(cat "$CURSOR" 2>/dev/null || echo 0)
case "$C" in ''|*[!0-9]*) C=0;; esac
[ "$N" -le "$C" ] && exit 0

SLICE=$(sed -n "$((C+1)),${N}p" "$EVENTS")

PROMPT=$(printf '%s\n' "$SLICE" | "$PY" "$HOOKS/build_card.py" prompt)
if [ -z "$PROMPT" ]; then
  echo "$N" > "$CURSOR"   # 解説対象の実装が無い -> 進めて終わる(claudeは呼ばない)
  exit 0
fi

# --- 翻訳(空ディレクトリで実行: 余計な CLAUDE.md を読ませない) ---
mkdir -p "$RUNDIR"
OUT=$(cd "$RUNDIR" && printf '%s' "$PROMPT" | env -u ANTHROPIC_API_KEY "$CLAUDE" -p --model "$MODEL" 2>>"$LOG")
if [ -z "$OUT" ]; then
  echo "$(date '+%F %T') claude empty output (cursor据え置き・次ターン再試行)" >> "$LOG"
  exit 0
fi

# --- プロジェクト名(最後のイベントの cwd ベース名) ---
PROJ=$(printf '%s\n' "$SLICE" | tail -1 | "$PY" -c "import sys,json,os,re
try:
    d=json.loads(sys.stdin.read() or '{}')
    cwd=(d.get('cwd','') or '')
    m=re.search(r'/GPT/([^/]+)', cwd)
    print(m.group(1) if m else (os.path.basename(cwd.rstrip('/')) or ''))
except Exception:
    print('')" 2>/dev/null)

# --- マージ(成功時のみカーソル前進) ---
if printf '%s' "$OUT" | "$PY" "$HOOKS/build_card.py" merge --data "$DATA" --view "$VIEW" --project "$PROJ" >>"$LOG" 2>&1; then
  echo "$N" > "$CURSOR"
  echo "$(date '+%F %T') ok up to line $N (proj=$PROJ)" >> "$LOG"
  # Google Driveバックアップ(大元はローカル維持・コピーをDriveへ。退避中で書けなければ黙ってskip)
  mkdir -p "$BACKUP" 2>/dev/null && cp "$DATA/cards.jsonl" "$DATA/terms.json" "$BACKUP/" 2>/dev/null || true
fi
exit 0

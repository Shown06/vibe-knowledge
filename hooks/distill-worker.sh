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
CONFIG="$VK_HOME/config.json"

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

# --- 課金主体の選択: デフォルトはサブスク(Claude Pro/Max)枠を消費。
# config.json の use_api_key が true の場合のみ ANTHROPIC_API_KEY を活かして従量課金APIを使う。
# 後方互換: config.json が無い/壊れている場合はデフォルト(サブスク消費=従来通り)のまま動く。
USE_API_KEY=$("$PY" -c "
import json
try:
    with open('$CONFIG', encoding='utf-8') as f:
        cfg = json.load(f)
    print('1' if cfg.get('use_api_key') else '0')
except Exception:
    print('0')
" 2>/dev/null)
[ "$USE_API_KEY" = "1" ] || USE_API_KEY=0

# --- 翻訳(空ディレクトリで実行: 余計な CLAUDE.md を読ませない) ---
mkdir -p "$RUNDIR"
if [ "$USE_API_KEY" = "1" ]; then
  OUT=$(cd "$RUNDIR" && printf '%s' "$PROMPT" | "$CLAUDE" -p --model "$MODEL" 2>>"$LOG")
else
  OUT=$(cd "$RUNDIR" && printf '%s' "$PROMPT" | env -u ANTHROPIC_API_KEY "$CLAUDE" -p --model "$MODEL" 2>>"$LOG")
fi
if [ -z "$OUT" ]; then
  echo "$(date '+%F %T') claude empty output (cursor据え置き・次ターン再試行)" >> "$LOG"
  exit 0
fi

# --- プロジェクト名(バッチ内の実装イベント cwd の最頻トップレベル) ---
# 旧実装は「最後のイベントの cwd basename」だけを見ていたため、cwd が GPT ルート・
# ファイルシステム root・作業用ディレクトリ(artifacts/tmp)・サブディレクトリ末端の時に
# 大量の誤分類(GPT/''/tmp/artifacts, moraeru-lp 等)を生んでいた。
# ここでは実装ツール(Edit/Write/... /Bash)のイベント cwd を GPT 直下トップレベルへ正規化し、
# その最頻値を採用する。scratch/root しか無いバッチは '(未分類)' にして無理に紐付けない。
PROJ=$(printf '%s\n' "$SLICE" | "$PY" -c "import sys,json,os,re,collections
IMPL={'Edit','Write','MultiEdit','NotebookEdit','Bash'}
SCRATCH={'artifacts','tmp','run','data','node_modules','.git','.claude','dist','_public','build','.wrangler','.next','worktrees','public','.cache','.venv','venv','out'}
def canon(cwd):
    if not cwd: return None
    m=re.search(r'/GPT/([^/]+)', cwd)
    if not m: return None
    seg=m.group(1)
    return None if seg in SCRATCH else seg
cnt=collections.Counter()
for line in sys.stdin:
    line=line.strip()
    if not line: continue
    try: d=json.loads(line)
    except Exception: continue
    if d.get('tool') not in IMPL: continue
    c=canon(d.get('cwd','') or '')
    if c: cnt[c]+=1
print(cnt.most_common(1)[0][0] if cnt else '(未分類)')" 2>/dev/null)
[ -n "$PROJ" ] || PROJ='(未分類)'

# --- マージ(成功時のみカーソル前進) ---
if printf '%s' "$OUT" | "$PY" "$HOOKS/build_card.py" merge --data "$DATA" --view "$VIEW" --project "$PROJ" >>"$LOG" 2>&1; then
  echo "$N" > "$CURSOR"
  echo "$(date '+%F %T') ok up to line $N (proj=$PROJ)" >> "$LOG"
  # Google Driveバックアップ(大元はローカル維持・コピーをDriveへ。退避中で書けなければ黙ってskip)
  mkdir -p "$BACKUP" 2>/dev/null && cp "$DATA/cards.jsonl" "$DATA/terms.json" "$BACKUP/" 2>/dev/null || true
fi
exit 0

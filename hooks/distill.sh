#!/usr/bin/env bash
# Vibe Knowledge - 翻訳ランチャー (Stop hook から呼ばれる)
# 即バックグラウンド化してフォアグラウンドは即終了する。
# -> ターンの応答を1秒も遅らせない。重い claude -p は裏で走らせる。
set -uo pipefail

DATA="$HOME/.claude/vibe-knowledge/data"
HOOKS="$HOME/.claude/hooks/vibe-knowledge"

[ -d "$DATA" ] || exit 0              # 未インストール/退避中
[ -n "${VK_DISTILLING:-}" ] && exit 0 # 翻訳プロセス自身からの再帰を防ぐ
[ -f "$HOOKS/distill-worker.sh" ] || exit 0

nohup bash "$HOOKS/distill-worker.sh" >/dev/null 2>&1 &
exit 0

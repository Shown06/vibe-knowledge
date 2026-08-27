#!/bin/bash
# Google Drive 再同期による .git 破損の定期検知（PayPay bot・vibe-knowledge で実発生）。
# git status / git log では検出できない（index と HEAD の tree は pack 側から読めるため）。
# 全オブジェクトを実読取し、3段で分類する:
#   pack_bad (.pack/.idx が読めない) = 致命 / loose_bad = 最後の gc 以降の履歴喪失 / rev_bad = キャッシュのみ実害なし
# 異常時のみ Telegram 総合窓口 bot へ通知。正常時は無通知(stdout にのみ出力)。
# launchd: com.reflow.vibe-knowledge-git-health (週1)
set -uo pipefail

REPO="${1:-/Users/two-de-sir/Library/CloudStorage/GoogleDrive-stateless.smallbroom@gmail.com/マイドライブ/株式会社ReFlow/GPT/vibe-knowledge}"
TG_ENV="$HOME/.claude/channels/telegram-whole/.env"
TG_CHAT="5764130230"

notify() {
  local token
  token=$(grep -E '^TELEGRAM_BOT_TOKEN=' "$TG_ENV" 2>/dev/null | cut -d= -f2- | tr -d '"'\''')
  [ -n "$token" ] || { echo "NOTIFY_FAILED: no token" >&2; return 1; }
  curl -sf -X POST "https://api.telegram.org/bot${token}/sendMessage" \
    -d chat_id="$TG_CHAT" --data-urlencode "text=$1" -o /dev/null --max-time 20 \
    || { echo "NOTIFY_FAILED: telegram send error" >&2; return 1; }
}

cd "$REPO" 2>/dev/null || { notify "[git健全性] 異常: リポジトリが開けない $REPO"; echo "REPO_MISSING"; exit 1; }
[ -d .git ] || { notify "[git健全性] 異常: .git が存在しない $REPO"; echo "GIT_MISSING"; exit 1; }

# ルースオブジェクト: cat-file で実体を読む(ファイルが dataless だと失敗する)
loose_total=0; loose_bad=0
while IFS= read -r f; do
  loose_total=$((loose_total+1))
  sha="$(basename "$(dirname "$f")")$(basename "$f")"
  git cat-file -p "$sha" >/dev/null 2>&1 || loose_bad=$((loose_bad+1))
done < <(find .git/objects -type f -path '*/??/*' 2>/dev/null)

# pack/idx/rev: ファイル本体を cat で materialize できるか
pack_total=0; pack_bad=0; rev_total=0; rev_bad=0
for f in .git/objects/pack/*; do
  [ -f "$f" ] || continue
  case "$f" in
    *.rev) rev_total=$((rev_total+1)); cat "$f" >/dev/null 2>&1 || rev_bad=$((rev_bad+1)) ;;
    *.pack|*.idx) pack_total=$((pack_total+1)); cat "$f" >/dev/null 2>&1 || pack_bad=$((pack_bad+1)) ;;
  esac
done

# HEAD の tree が実際に辿れるか
tree_ok=OK
git cat-file -p 'HEAD^{tree}' >/dev/null 2>&1 || tree_ok=NG

# origin 疎通(ネットワーク障害と破損を混同しないよう別項目として扱う)
remote_ok=REMOTE_OK
git ls-remote origin >/dev/null 2>&1 || remote_ok=REMOTE_NG

report="repo=$REPO
loose_bad=$loose_bad/$loose_total pack_bad=$pack_bad/$pack_total rev_bad=$rev_bad/$rev_total
HEAD_tree=$tree_ok origin=$remote_ok"
echo "$(date '+%F %T') $report"

if [ "$pack_bad" -gt 0 ] || [ "$loose_bad" -gt 0 ] || [ "$tree_ok" = NG ] || [ "$remote_ok" = REMOTE_NG ]; then
  notify "[git健全性] 異常検知 vibe-knowledge
$report
※pack_bad>0 は致命(origin から再取得)・loose_bad>0 は最後のgc以降の履歴喪失・rev_bad のみなら実害なし"
  exit 2
fi
exit 0

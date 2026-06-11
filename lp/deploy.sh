#!/usr/bin/env bash
# Vibe Knowledge LP — Cloudflare Pages デプロイスクリプト
# 使い方: bash lp/deploy.sh
set -euo pipefail

LP_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT="vibe-knowledge-lp"

echo "=== [1/4] KV namespace 確認 ==="
if ! wrangler kv namespace list 2>/dev/null | grep -q "WAITLIST"; then
  echo "KV namespace を作成します..."
  OUTPUT=$(wrangler kv namespace create WAITLIST 2>&1)
  echo "$OUTPUT"
  KV_ID=$(echo "$OUTPUT" | grep -oE '"id": "[^"]+"' | head -1 | grep -oE '"[^"]+":' | tail -1 | tr -d '": ')
  echo "wrangler.toml の id を更新: $KV_ID"
  sed -i '' "s/REPLACE_WITH_KV_NAMESPACE_ID/$KV_ID/" "$LP_DIR/wrangler.toml"
else
  echo "[OK] KV namespace 既存"
fi

echo "=== [2/4] secrets 確認 ==="
for SECRET in RESEND_API_KEY NOTIFY_EMAIL ADMIN_TOKEN; do
  if ! wrangler pages secret list --project-name "$PROJECT" 2>/dev/null | grep -q "$SECRET"; then
    echo "設定が必要: wrangler pages secret put $SECRET --project-name $PROJECT"
  else
    echo "[OK] $SECRET 設定済み"
  fi
done

echo "=== [3/4] Pages プロジェクトへデプロイ ==="
cd "$LP_DIR"
wrangler pages deploy . --project-name "$PROJECT" --branch main

echo "=== [4/4] デプロイ確認 ==="
DEPLOY_URL=$(wrangler pages deployment list --project-name "$PROJECT" 2>/dev/null | grep -oE 'https://[a-z0-9-]+\.pages\.dev' | head -1)
echo "URL: ${DEPLOY_URL:-https://vibe-knowledge-lp.pages.dev}"
echo ""
echo "ウェイトリスト確認:"
echo "  curl '${DEPLOY_URL:-https://vibe-knowledge-lp.pages.dev}/api/waitlist?token=YOUR_ADMIN_TOKEN'"

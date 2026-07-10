# Vibe Knowledge（バイブナレッジ）

> **北極星**: 自分がバイブコーディングで作ったものを理解し、商談で自分の言葉で説明できるようになる。実装を自動でやさしいカードに翻訳し、プロジェクト別に整理して、勉強しながら貯める。（→ [GOAL.md](GOAL.md)）

バイブコーディングの裏返し。**あなたが指示して作ったコードを、そのつど「小6〜中1にも分かる言葉」に翻訳して貯めていく学習レイヤー。**
新しい勉強アプリを開くのではなく、いまの Claude Code 実装フローに寄生して動く。普段どおり喋って作らせるだけで、知識カードが勝手に増える。

## 仕組み（3層）

| 層 | 役割 | 実体 | コスト |
|---|---|---|---|
| ① 捕捉 | 実装イベント(Edit/Write/Bash 等)を軽量ログ化 | `capture.py`（PostToolUse hook） | ゼロ（claude を呼ばない） |
| ② 翻訳 | ターン区切りで「中1向けカード」に変換 | `distill.sh` → `distill-worker.sh` → `build_card.py`（Stop hook・裏で `claude -p` haiku） | サブスク内（`ANTHROPIC_API_KEY` を外して実行） |
| ③ 蓄積・復習 | カード／用語集／概念マップ／復習クイズ | `view/index.html`（バニラJS・間隔反復は localStorage） | ゼロ |

- **実装イベントが無いターンでは `claude` を呼ばない**（雑談ターンで課金しない）。
- **翻訳は裏でバックグラウンド実行**。ターンの応答を1秒も遅らせない。
- **自己再帰しない**（翻訳プロセスが出すイベントは `VK_DISTILLING` ガードで無視）。

## 置き場所（Google Drive 退避対策）

| 種類 | パス | 理由 |
|---|---|---|
| スクリプト本体（稼働） | `~/.claude/hooks/vibe-knowledge/` | 安定領域。Drive 退避で毎ターン落ちるのを防ぐ |
| 生データ | `~/.claude/vibe-knowledge/data/` | 消えたら困るので安定領域 |
| 正本ソース・閲覧UI | `GPT/vibe-knowledge/`（このフォルダ） | 編集・閲覧する場所。`install.sh` で安定領域へ展開 |

閲覧UIの `data.js` は翻訳のたびに再生成される（再生成可能なので Drive 上でOK）。退避中は書き込みを黙ってスキップし、復帰後に追いつく。

## 使い方

```bash
# 0) リリースタグを指定してclone（mainを直接使わず、固定バージョンで導入する）
git clone https://github.com/Shown06/vibe-knowledge
cd vibe-knowledge
git checkout v1.1.0

# 1) インストール（スクリプト展開 + settings.json へ hook 登録。既存hookは壊さない）
bash install.sh

# 2) あとは普段どおり Claude Code で実装するだけ。
#    Edit/Write/Bash を含むターンを終えるたび、裏でカードが増える。

# 3) 見る
open view/index.html   # ブラウザで開く（カード / 用語集 / 概念マップ / 復習クイズ）
```

### install.sh が実際にやること

| ステップ | 内容 | 場所 |
|---|---|---|
| 1 | `capture.py`・`build_card.py`・`distill.sh`・`distill-worker.sh` をコピー | `~/.claude/hooks/vibe-knowledge/`（新規ファイル） |
| 2 | データディレクトリを作成 | `~/.claude/vibe-knowledge/data/`（新規ファイル: `events.jsonl`・`.cursor`） |
| 3 | `settings.json` をバックアップした上で編集 | `~/.claude/settings.json` → `PostToolUse` hook（`capture.py` 実行）と `Stop` hook（`distill.sh` 実行）を追加。**この直前に何を追加するかを表示した上で `[y/N]` の確認**を求める。バックアップ（`settings.json.bak-vk-<タイムスタンプ>`）は回答に関わらず先に作成される。ここで`N`と答えても他のステップは全て完了し、インストール自体は終わる（hookの有効化は後からでも可能・その手順を画面に表示する） |
| 4 | 変更後の `settings.json` が正しい JSON か検証 | — |
| 5 | 任意で MCP サーバーをビルド・登録 | `claude mcp add vibe-knowledge …` |

いずれの段階でも外部への送信は発生しない（capture・distill・閲覧UIはすべてローカル実行）。

Webサイト記載のように `curl` で直接インストーラーを取得する場合は、`main` ではなく**固定されたリリースタグ**を必ず使うこと:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/Shown06/vibe-knowledge/refs/tags/v1.1.0/install.sh)
```

タグは改変されない固定参照のため、実行されるコードは常に該当[リリース](https://github.com/Shown06/vibe-knowledge/releases)の内容と一致し、後から中身が変わることはない。リリース一覧: https://github.com/Shown06/vibe-knowledge/releases

### 手動でいますぐ翻訳したいとき

```bash
bash ~/.claude/hooks/vibe-knowledge/distill-worker.sh
```

### アンインストール

`~/.claude/settings.json` の PostToolUse から `capture.py`、Stop から `distill.sh` の項目を消す（`install.sh` 実行時に `settings.json.bak-vk-*` を自動保存している）。

## データ形式

- `data/events.jsonl` … 捕捉した生イベント（1行1件）
- `data/cards.jsonl` … 生成カード（1行1枚）
- `data/terms.json` … 用語集（出現回数・関連語・SRS初期値）
- `data/.cursor` … 翻訳済みの行数（カーソル）
- `data/distill.log` … 翻訳ログ（失敗診断用）

## カード1枚の中身

```json
{
  "term": "Webhook", "reading": "ウェブフック",
  "easy": "何かが起きたら、自動で相手に知らせる仕組み。",
  "why": "支払いが完了したことを自動でサーバーに伝えるために使った。",
  "analogy": "ピンポンが鳴ったら出る、の『鳴らす側』の仕組み。",
  "related": ["API", "サーバー", "イベント"],
  "code_ref": "stripe webhook handler"
}
```

## 安全・制限（正直な線引き）

- **秘密マスク**: `.env`／`*.key`／`*.pem`／`local.properties` などの機密ファイルは内容を一切記録しない。本文中の API キー・トークン・`password=`／`Bearer …`／秘密鍵は `capture.py` が `[秘密マスク]` に伏字化してから保存する（events・cards に平文の鍵を残さない／haiku にも送らない）。
- **1ターン150件まで**: 1ターンに150を超える実装イベントがあると、新しい順150件だけを翻訳対象にする（消化不良を避ける意図的な上限。超過分は二度目には拾わない）。
- **events.jsonl は追記式**: 長期で肥大する。気になったら `data/events.jsonl` を空にして `data/.cursor` を `0` に戻せばリセットできる（カード自体は `cards.jsonl` に残る）。
- **1 distill = 最大4枚**: 毎ターン最大4枚ずつ貯める設計（中1が1日に覚える量として適量）。

## 製品化メモ（ツルハシ）

バイブコーダー（Claude Code / Cursor ユーザー）全員が潜在顧客。「作れるけど中で何が起きてるか分からない」不安は今いちばんホットな痛点。
まず Shown 自身の実装で1〜2週間回し、効くと確認できたら `install.sh` 一式を配布物にする。`distill-worker.sh` 内の `VIEW` パスを `install.sh` 側で書き換える方式にすれば、他環境へそのまま展開できる。

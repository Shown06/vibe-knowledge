#!/usr/bin/env python3
"""Vibe Knowledge - 翻訳カードのコア
2モード:
  prompt : stdin(events jsonl) -> 中1向け解説を作らせるプロンプト(stdout)
  merge  : stdin(claude出力)   -> cards.jsonl / terms.json / data.js を更新

prompt が空文字を返したら「解説対象の実装が無い」= 呼び出し側は claude を呼ばずに終える。
"""
import sys
import os
import re
import json
import argparse
import datetime

IMPL_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit", "Bash"}

PROMPT_TEMPLATE = """あなたは「バイブナレッジ」の編集者です。
このツールの持ち主は、自分ではコードを書かず AI に作らせている人(バイブコーダー)で、エンジニアではありません。
ゴールは、その人が「自分が作ったものを理解し、商談でお客さんに自分の言葉で説明し、質問に答えられる」ようになること。

各カードには2つの役割があります:
(1) まず本人が「これは何か」を、専門知識ゼロでも腑に落ちるように理解する。
(2) さらに、それを商談でお客さんに説明し、つっこんだ質問にも答えられるようにする。

# 守ること
- むずかしい言葉(専門用語)は、必ず「やさしい言いかえ」とセットにする。
- たとえ話は、日常のもの(電話・手紙・お店・かぎ・地図・引き出し など)を使う。
- 1つの新しい言葉につき、カードを1枚。今回はじめて出てきた大事な言葉だけ(最大4枚)。当たり前のもの(ファイルを保存した等)はカードにしない。
- ウソを書かない。確かでないことは書かない。絵文字は使わない。「実は〜」等の雰囲気だけの言い回しは使わない。
- explain と qa は、お客さんの前で実際に口に出せる自然な言い方にする。かしこまりすぎず、専門用語を1つ自分の言葉で使い、自信をもって言える形に。盛らない・嘘をつかない。

# たった今の開発作業
{body}

# 出力(これだけを返す。前後に文章を書かない)
次の形のJSON配列だけを出力してください:
[
  {{
    "term": "出てきた言葉(英語やカタカナのまま。例: Webhook)",
    "reading": "読みがな(例: ウェブフック)",
    "easy": "それが何かをやさしく2〜3文で。小6にも分かる言葉で。",
    "why": "なぜ今回それを使ったのか、この作業での役わりを1〜2文で。",
    "analogy": "日常のものでのたとえを1文で。",
    "explain": "商談でお客さんに説明するときの言い方。専門用語を1つ自分の言葉で使い、相手にも伝わるよう自信をもって言える1〜2文。",
    "qa": [{{"q": "お客さんが聞いてきそうな質問(例: それ安全なの?)", "a": "それにどう答えるか。自分の言葉で1〜2文"}}],
    "related": ["関係する言葉", "..."],
    "code_ref": "どのファイルやコマンドの話か(例: capture.py / git commit)"
  }}
]
今回カードにすべき新しい言葉が無ければ [] だけを返してください。
"""


def today():
    return datetime.date.today().isoformat()


def now_iso():
    return datetime.datetime.now().isoformat(timespec="seconds")


def load_jsonl(path):
    out = []
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except Exception:
                    pass
    return out


def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default
    return default


# ---------------- prompt ----------------

def build_prompt(events):
    impl = [e for e in events if e.get("tool") in IMPL_TOOLS]
    if not impl:
        return ""
    lines = []
    for e in impl:
        t = e.get("tool")
        s = (e.get("summary", "") or "").strip()
        d = (e.get("detail", "") or "").strip().replace("\n", " ")
        if t == "Bash":
            line = f"- ターミナルで実行: `{s}`"
            if d:
                line += f"  (目的: {d})"
        else:
            line = f"- ファイルを編集 [{s}]"
            if d:
                line += f": {d[:200]}"
        lines.append(line)
    # 1ターンあたり上限。これを超える超大量ターンでは新しい順150件を翻訳対象にする。
    if len(lines) > 150:
        lines = lines[-150:]
    body = "\n".join(lines)
    return PROMPT_TEMPLATE.format(body=body)


# ---------------- merge ----------------

def extract_json_array(text):
    if not text:
        return []
    m = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, re.S)
    raw = m.group(1) if m else None
    if raw is None:
        s = text.find("[")
        e = text.rfind("]")
        if s != -1 and e != -1 and e > s:
            raw = text[s:e + 1]
    if raw is None:
        return []
    try:
        data = json.loads(raw)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def init_srs():
    # SM-2 簡易版。interval=0 は「まだ一度も復習していない=すぐ出題対象」
    return {"ease": 2.5, "interval": 0, "due": today(), "reps": 0}


def project_name(cwd):
    if not cwd:
        return ""
    base = os.path.basename(cwd.rstrip("/"))
    return base or cwd


DUP_SUPPRESS_DAYS = 14


def merge(cards_new, data_dir, view_dir, project):
    os.makedirs(data_dir, exist_ok=True)
    cards_path = os.path.join(data_dir, "cards.jsonl")
    terms_path = os.path.join(data_dir, "terms.json")
    terms = load_json(terms_path, {})

    added = []
    td = today()
    ts = now_iso()
    today_date = datetime.date.today()
    proj_key = project or ""

    with open(cards_path, "a", encoding="utf-8") as cf:
        for c in cards_new:
            if not isinstance(c, dict):
                continue
            term = (c.get("term") or "").strip()
            if not term:
                continue
            related = c.get("related") or []
            if not isinstance(related, list):
                related = []
            qa_raw = c.get("qa") or []
            if not isinstance(qa_raw, list):
                qa_raw = []
            qa = [{"q": str(x.get("q", "")), "a": str(x.get("a", ""))}
                  for x in qa_raw if isinstance(x, dict) and x.get("q")]

            # --- 生成時点での重複抑制(コード側で判定・LLMには任せない) ---
            # 同一プロジェクトで直近 DUP_SUPPRESS_DAYS 日以内に同じ用語が既出なら、
            # cards.jsonl への新規追記はスキップし、terms.json の count/last_seen/related だけ更新する。
            # 別プロジェクトでの初出、または同一プロジェクトでも期間超の再登場は
            # 文脈の違いに価値があるため通常通り新規カードとして追記する。
            skip_new_card = False
            existing = terms.get(term)
            if existing:
                seen_by_proj = existing.get("last_seen_by_project", {}) or {}
                last_seen_for_proj = seen_by_proj.get(proj_key)
                if last_seen_for_proj:
                    try:
                        last_dt = datetime.date.fromisoformat(last_seen_for_proj)
                        if (today_date - last_dt).days < DUP_SUPPRESS_DAYS:
                            skip_new_card = True
                    except Exception:
                        pass

            if not skip_new_card:
                card = {
                    "id": f"{td}-{len(added)}-{abs(hash(term + ts)) % 1000000}",
                    "ts": ts,
                    "project": project,
                    "term": term,
                    "reading": c.get("reading", ""),
                    "easy": c.get("easy", ""),
                    "why": c.get("why", ""),
                    "analogy": c.get("analogy", ""),
                    "explain": c.get("explain", ""),
                    "qa": qa,
                    "related": related,
                    "code_ref": c.get("code_ref", ""),
                }
                cf.write(json.dumps(card, ensure_ascii=False) + "\n")
                added.append(card)

            if term in terms:
                terms[term]["count"] = terms[term].get("count", 1) + 1
                terms[term]["last_seen"] = td
                rel = set(terms[term].get("related", [])) | set(related)
                terms[term]["related"] = sorted(x for x in rel if x)
            else:
                terms[term] = {
                    "reading": c.get("reading", ""),
                    "definition": c.get("easy", ""),
                    "analogy": c.get("analogy", ""),
                    "first_seen": td,
                    "last_seen": td,
                    "count": 1,
                    "related": sorted(x for x in related if x),
                    "srs": init_srs(),
                }

            # プロジェクト別の直近既出トラッキング(次回以降の重複抑制判定に使う)
            terms[term]["last_project"] = project
            seen_by_proj = terms[term].setdefault("last_seen_by_project", {})
            seen_by_proj[proj_key] = td

    with open(terms_path, "w", encoding="utf-8") as f:
        json.dump(terms, f, ensure_ascii=False, indent=2)

    rebuild_view(data_dir, view_dir)
    return added


def rebuild_view(data_dir, view_dir):
    """cards.jsonl + terms.json を view/data.js(window.VK_DATA) に書き出す。
    file:// で開いても読めるよう <script src> 形式。Drive退避で書けない時は黙ってskip。"""
    if not view_dir:
        return
    try:
        cards = load_jsonl(os.path.join(data_dir, "cards.jsonl"))
        terms = load_json(os.path.join(data_dir, "terms.json"), {})
        data = {
            "cards": cards,
            "terms": terms,
            "generated": now_iso(),
            "counts": {"cards": len(cards), "terms": len(terms)},
        }
        os.makedirs(view_dir, exist_ok=True)
        payload = "window.VK_DATA = " + json.dumps(data, ensure_ascii=False) + ";\n"
        with open(os.path.join(view_dir, "data.js"), "w", encoding="utf-8") as f:
            f.write(payload)
    except Exception:
        return


# ---------------- main ----------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["prompt", "merge"])
    ap.add_argument("--data", default=os.path.expanduser("~/.claude/vibe-knowledge/data"))
    ap.add_argument("--view", default="")
    ap.add_argument("--project", default="")
    args = ap.parse_args()

    if args.cmd == "prompt":
        events = []
        for line in sys.stdin:
            line = line.strip()
            if line:
                try:
                    events.append(json.loads(line))
                except Exception:
                    pass
        out = build_prompt(events)
        sys.stdout.write(out)
        # 解説対象が無い時は空 -> 呼び出し側で claude を呼ばずに終える
        return 0 if out else 3

    if args.cmd == "merge":
        text = sys.stdin.read()
        cards = extract_json_array(text)
        added = merge(cards, args.data, args.view, args.project)
        sys.stderr.write(f"[vibe-knowledge] merged {len(added)} card(s)\n")
        return 0


if __name__ == "__main__":
    sys.exit(main())

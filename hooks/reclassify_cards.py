#!/usr/bin/env python3
"""Vibe Knowledge - 既存カードの project 再分類バッチ（決定論・fail-closed）

背景:
  distill-worker.sh は「バッチ最後のイベントの cwd」から project を決めていた。
  そのためセッションの cwd が GPT ルート('GPT')・ファイルシステム root('')・
  作業用ディレクトリ('artifacts'/'tmp')・サブディレクトリ末端('moraeru-lp' 等)の時に
  誤分類が大量発生した(実測: GPT=817, ''=155, tmp=10, artifacts=8 ほか)。

再分類の証拠源(捏造しない):
  1) distill.log の "ok up to line N (proj=X)" 行 = 各 distill バッチの
     (タイムスタンプ, 到達行N, 当時の project)。タイムスタンプは card.ts と一致する。
  2) events.jsonl の各行 = 実イベント(cwd 付き)。バッチの行範囲内の
     実装イベント(Edit/Write/MultiEdit/NotebookEdit/Bash)の cwd から、
     GPT 直下トップレベルの最頻プロジェクトを「真の project」として復元する。

解決順(各カード):
  A. 既に正当なトップレベル project ならそのまま(keep)
  B. バッチ復元: (card.ts, card.project) でバッチを引き当て、実装イベント cwd 最頻から復元
  C. basename ロールアップ: 末端名→唯一の親が events から確定できる場合のみ親に付け替え
  D. いずれも不可 → '(未分類)' として unmatched.jsonl に記録(無理に紐付けない)

使い方:
  python3 reclassify_cards.py            # dry-run(変更しない・件数レポートのみ)
  python3 reclassify_cards.py --apply    # バックアップを取って cards.jsonl を書き換え、data.js 再生成
"""
import argparse
import collections
import datetime
import json
import os
import re
import shutil
import sys

VK_DATA = os.path.expanduser("~/.claude/vibe-knowledge/data")
VIEW = "/Users/two-de-sir/マイドライブ/株式会社ReFlow/GPT/vibe-knowledge/view"
GPT_ROOT = "/Users/two-de-sir/マイドライブ/株式会社ReFlow/GPT"

IMPL = {"Edit", "Write", "MultiEdit", "NotebookEdit", "Bash"}
# GPT 直下だが「プロジェクトではない」作業用/生成物/ツール系ディレクトリ名
SCRATCH = {
    "artifacts", "tmp", "run", "data", "node_modules", ".git", ".claude",
    "dist", "_public", "build", ".wrangler", ".next", "worktrees", "public",
    ".cache", ".venv", "venv", "out",
}
# cwd から復元できなかった時に付ける不明ラベル
UNCLASSIFIED = "(未分類)"


def canon(cwd):
    """cwd → GPT 直下トップレベルのプロジェクト名(scratch/root は None)。"""
    if not cwd:
        return None
    m = re.search(r"/GPT/([^/]+)", cwd)
    if not m:
        return None
    seg = m.group(1)
    if seg in SCRATCH:
        return None
    return seg


def load_events(path):
    """1-based の行配列で返す(ev[0] はダミー)。"""
    ev = [None]
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                ev.append({})
                continue
            try:
                ev.append(json.loads(line))
            except Exception:
                ev.append({})
    return ev


def build_batches(distill_log, events):
    """distill.log からバッチ列を復元し、各バッチの復元 project を計算。"""
    batches = []
    prev = 0
    n_ev = len(events) - 1
    with open(distill_log, encoding="utf-8") as f:
        for line in f:
            m = re.match(
                r"(\d{4}-\d\d-\d\d) (\d\d:\d\d:\d\d) ok up to line (\d+) \(proj=(.*)\)\s*$",
                line,
            )
            if not m:
                continue
            d, t, N, proj = m.group(1), m.group(2), int(m.group(3)), m.group(4)
            ts = f"{d}T{t}"
            start, end = prev + 1, N
            prev = N
            cnt = collections.Counter()
            for i in range(start, min(end, n_ev) + 1):
                if i < 1 or i >= len(events):
                    continue
                e = events[i]
                if not e or e.get("tool") not in IMPL:
                    continue
                c = canon(e.get("cwd", "") or "")
                if c:
                    cnt[c] += 1
            recovered = cnt.most_common(1)[0][0] if cnt else None
            batches.append({"ts": ts, "proj": proj, "recovered": recovered})
    return batches


def parse_ts(ts):
    try:
        return datetime.datetime.fromisoformat(ts)
    except Exception:
        return None


def build_valid_projects(events):
    """正当なプロジェクト名集合 = 物理トップレベル dir ∪ events のトップレベル segment。"""
    valid = set()
    # 物理ディレクトリ(空白入りの日本語名も保持)
    if os.path.isdir(GPT_ROOT):
        for name in os.listdir(GPT_ROOT):
            if os.path.isdir(os.path.join(GPT_ROOT, name)) and name not in SCRATCH:
                valid.add(name)
    # events に現れたトップレベル segment(過去に存在した/改名された project も救う)
    for e in events:
        if not e:
            continue
        c = canon(e.get("cwd", "") or "")
        if c:
            valid.add(c)
    return valid


def build_basename_map(events):
    """末端ディレクトリ名 → 親トップレベル。唯一に確定するものだけ返す。"""
    bmap = collections.defaultdict(set)
    seen = set()
    for e in events:
        if not e:
            continue
        cwd = e.get("cwd", "") or ""
        if cwd in seen:
            continue
        seen.add(cwd)
        top = canon(cwd)
        base = os.path.basename(cwd.rstrip("/"))
        if top and base and base != top and base not in SCRATCH:
            bmap[base].add(top)
    return {k: next(iter(v)) for k, v in bmap.items() if len(v) == 1}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=VK_DATA)
    ap.add_argument("--view", default=VIEW)
    ap.add_argument("--apply", action="store_true", help="実際に書き換える(既定はdry-run)")
    ap.add_argument("--tolerance", type=int, default=2, help="ts一致の許容秒(バッチ結合)")
    args = ap.parse_args()

    cards_path = os.path.join(args.data, "cards.jsonl")
    events_path = os.path.join(args.data, "events.jsonl")
    distill_log = os.path.join(args.data, "distill.log")
    for p in (cards_path, events_path, distill_log):
        if not os.path.exists(p):
            print(f"[FATAL] 必須ファイルが無い: {p}", file=sys.stderr)
            return 2

    events = load_events(events_path)
    valid = build_valid_projects(events)
    bmap = build_basename_map(events)
    batches = build_batches(distill_log, events)

    # バッチ索引: (ts,proj)→recovered(完全一致) と、proj別のtsソート列(許容一致用)
    exact = {}
    by_proj = collections.defaultdict(list)
    for b in batches:
        exact.setdefault((b["ts"], b["proj"]), b["recovered"])
        dt = parse_ts(b["ts"])
        if dt is not None:
            by_proj[b["proj"]].append((dt, b["recovered"]))
    for k in by_proj:
        by_proj[k].sort()

    def batch_recover(ts, proj):
        if (ts, proj) in exact:
            return exact[(ts, proj)]
        dt = parse_ts(ts)
        if dt is None:
            return None
        best = None
        bestdiff = None
        for bdt, rec in by_proj.get(proj, []):
            diff = abs((bdt - dt).total_seconds())
            if diff <= args.tolerance and (bestdiff is None or diff < bestdiff):
                best, bestdiff = rec, diff
        return best

    def is_junk(p):
        return (p in ("", "GPT", "/", UNCLASSIFIED)) or (p in SCRATCH)

    # カード読み込み + 再分類判定
    cards = []
    with open(cards_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                cards.append(json.loads(line))
            except Exception:
                pass

    before = collections.Counter(c.get("project", "") for c in cards)
    reason = collections.Counter()
    unmatched = []
    changed = 0

    for c in cards:
        p = (c.get("project") or "")
        # A. 既に正当なトップレベル project → keep
        if not is_junk(p) and p in valid:
            reason["keep_valid"] += 1
            continue
        newp = None
        r = None
        # B. バッチ復元
        rec = batch_recover(c.get("ts", ""), p)
        if rec and rec in valid and not is_junk(rec):
            newp, r = rec, "batch_recover"
        # C. basename ロールアップ
        if newp is None and p in bmap and bmap[p] in valid:
            newp, r = bmap[p], "basename_rollup"
        # D. 不明 → (未分類) + unmatched 記録
        if newp is None:
            newp, r = UNCLASSIFIED, "unmatched"
            unmatched.append({"id": c.get("id"), "ts": c.get("ts"),
                              "orig_project": p, "term": c.get("term"),
                              "code_ref": c.get("code_ref", "")})
        reason[r] += 1
        if newp != p:
            c["project"] = newp
            changed += 1

    after = collections.Counter(c.get("project", "") for c in cards)

    # --- レポート ---
    def show(title, cnt):
        print(f"\n=== {title} (project別) ===")
        for k, v in cnt.most_common():
            print(f"  {v:5d}  {k!r}")

    print(f"総カード数: {len(cards)}")
    print(f"変更対象: {changed}  /  据え置き: {len(cards) - changed}")
    print("\n=== 判定内訳 ===")
    for k, v in reason.most_common():
        print(f"  {v:5d}  {k}")
    show("BEFORE", before)
    show("AFTER", after)
    junk_before = sum(v for k, v in before.items() if is_junk(k))
    junk_after = sum(v for k, v in after.items() if is_junk(k) and k != UNCLASSIFIED)
    unc_after = after.get(UNCLASSIFIED, 0)
    print(f"\n誤分類(ジャンク/scratchラベル): BEFORE {junk_before} -> AFTER {junk_after} "
          f"(+ (未分類)={unc_after})")
    print(f"unmatched(復元不能で未分類に退避): {len(unmatched)}")

    if not args.apply:
        print("\n[dry-run] 変更は書き込んでいない。適用するには --apply を付ける。")
        return 0

    # --- 適用: バックアップ → 原子的書き換え → data.js 再生成 ---
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = f"{cards_path}.bak-reclassify-{stamp}"
    shutil.copy2(cards_path, bak)
    print(f"\n[backup] {bak}")

    tmp = cards_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        for c in cards:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    os.replace(tmp, cards_path)
    print(f"[write] {cards_path} ({len(cards)} cards)")

    un_path = os.path.join(args.data, f"unmatched-{stamp}.jsonl")
    with open(un_path, "w", encoding="utf-8") as f:
        for u in unmatched:
            f.write(json.dumps(u, ensure_ascii=False) + "\n")
    print(f"[write] {un_path} ({len(unmatched)} unmatched)")

    # ダッシュボード(view/data.js)再生成: build_card の実装を流用
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import build_card
        build_card.rebuild_view(args.data, args.view)
        print(f"[view] {os.path.join(args.view, 'data.js')} を再生成")
    except Exception as e:
        print(f"[view] data.js 再生成に失敗(手動確認要): {e}", file=sys.stderr)

    print("\n[done] 再分類を適用した。")
    return 0


if __name__ == "__main__":
    sys.exit(main())

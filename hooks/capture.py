#!/usr/bin/env python3
"""Vibe Knowledge - 捕捉(capture)
PostToolUse hook。実装系ツール(Edit/Write/MultiEdit/Bash/NotebookEdit)が走るたびに、
「何が起きたか」だけを軽量に events.jsonl へ追記する。claude は呼ばない=コストゼロ。
解説生成(翻訳)は別フェーズ(distill.sh)がターン区切りでまとめて行う。
"""
import sys
import os
import re
import json
import datetime

DATA = os.path.expanduser("~/.claude/vibe-knowledge/data")
CONFIG_PATH = os.path.expanduser("~/.claude/vibe-knowledge/config.json")
IMPL_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit", "Bash"}


def _is_excluded_cwd(cwd):
    """NDA/秘密保持のためのプロジェクト単位ブロックリスト判定。
    config.json の exclude_paths に含まれる文字列のいずれかが cwd の部分文字列なら True。
    fail-open: config.json が無い/壊れている場合は「除外なし」として通常通り動作する
    (これはブロックリストであり、動かないより除外リストが空でも動く方が壊れにくいため)。
    TODO(将来検討): ブロックリストは列挙し忘れに弱い。NDA案件が増えるなら
    「明示的に許可したパスだけ捕捉する」allowlist 方式への切り替えを検討する余地がある。
    """
    if not cwd:
        return False
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            cfg = json.load(f)
        excludes = cfg.get("exclude_paths", []) or []
    except Exception:
        return False
    return any(p and p in cwd for p in excludes)

# --- 秘密マスク(平文の鍵・トークンを events/cards に残さない・haikuにも送らない) ---
SECRET_FILE_RE = re.compile(
    r"(^\.env|\.env\.|/\.env|secret|credential|password|\.pem$|\.key$|id_rsa|\.p12|keystore|"
    r"local\.properties|\.npmrc|\.pgpass|\.htpasswd)", re.I)
SECRET_VAL_RE = re.compile(
    r"(sk-[A-Za-z0-9]{8,}|sk_live_[A-Za-z0-9]+|sk_test_[A-Za-z0-9]+|whsec_[A-Za-z0-9]+|"
    r"rk_live_[A-Za-z0-9]+|ghp_[A-Za-z0-9]+|github_pat_[A-Za-z0-9_]+|xox[baprs]-[A-Za-z0-9-]+|"
    r"AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z\-_]{20,}|ya29\.[0-9A-Za-z\-_]+|"
    r"Bearer\s+[A-Za-z0-9._\-]+|eyJ[A-Za-z0-9._\-]{20,}|-----BEGIN[ A-Z]+PRIVATE KEY-----)")
SECRET_KV_RE = re.compile(
    r"(?i)\b(pass(?:word|wd)?|secret|token|api[_-]?key|access[_-]?key|"
    r"private[_-]?key|client[_-]?secret|auth[_-]?token)\b\s*[=:]\s*['\"]?[^\s'\"]{4,}")


def _kv_mask(m):
    raw = m.group(0)
    sep = "=" if "=" in raw else ":"
    key = re.split(r"[=:]", raw, maxsplit=1)[0]
    return f"{key}{sep}[秘密マスク]"


def sanitize(text):
    if not text:
        return text
    text = SECRET_VAL_RE.sub("[秘密マスク]", text)
    text = SECRET_KV_RE.sub(_kv_mask, text)
    return text


def main():
    # distill(翻訳)中に出たイベントは拾わない(自己再帰の防止)
    if os.environ.get("VK_DISTILLING"):
        return
    # データ領域が無い(=未インストール or Drive退避中)なら静かに何もしない
    if not os.path.isdir(DATA):
        return
    try:
        ev = json.load(sys.stdin)
    except Exception:
        return

    cwd = ev.get("cwd", "")
    if _is_excluded_cwd(cwd):
        return

    tool = ev.get("tool_name", "")
    if tool not in IMPL_TOOLS:
        return

    ti = ev.get("tool_input", {}) or {}
    summary = ""
    detail = ""

    if tool == "Bash":
        summary = (ti.get("command", "") or "")[:400]
        detail = (ti.get("description", "") or "")[:200]
    elif tool in {"Edit", "MultiEdit"}:
        summary = os.path.basename(ti.get("file_path", "") or "")
        new_s = ti.get("new_string", "") or ""
        if not new_s and ti.get("edits"):
            # MultiEdit
            try:
                new_s = "\n".join((e.get("new_string", "") or "") for e in ti["edits"])
            except Exception:
                new_s = ""
        detail = new_s[:400]
    elif tool == "Write":
        summary = os.path.basename(ti.get("file_path", "") or "")
        detail = (ti.get("content", "") or "")[:400]
    elif tool == "NotebookEdit":
        summary = os.path.basename(ti.get("notebook_path", "") or "")
        detail = (ti.get("new_source", "") or "")[:400]

    # 秘密マスク: 機密ファイルは内容を一切残さず、本文中の鍵/トークンは伏字化
    fp = ti.get("file_path", "") or ti.get("notebook_path", "") or ""
    # MultiEdit の場合は edits 配列内の各 file_path も検査する
    if tool == "MultiEdit":
        for edit in (ti.get("edits") or []):
            efp = edit.get("file_path", "") or ""
            if efp and SECRET_FILE_RE.search(os.path.basename(efp)):
                fp = efp  # 1つでも機密ファイルがあれば detail を消す
                break
    if fp and SECRET_FILE_RE.search(os.path.basename(fp)):
        detail = "(機密ファイルのため内容は記録しません)"
    summary = sanitize(summary)
    detail = sanitize(detail)

    rec = {
        "ts": datetime.datetime.now().isoformat(timespec="seconds"),
        "tool": tool,
        "summary": summary,
        "detail": detail,
        "cwd": ev.get("cwd", ""),
        "session": ev.get("session_id", ""),
    }
    try:
        os.makedirs(DATA, exist_ok=True)
        with open(os.path.join(DATA, "events.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        # 書けない(退避中など)なら黙って諦める。学習は止まらない設計。
        return


if __name__ == "__main__":
    main()

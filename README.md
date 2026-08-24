# Vibe Knowledge

> Your vibe-coding sessions, automatically turned into flashcards.

The reverse of vibe-coding.  
Every time you build something with Claude Code, Vibe Knowledge silently translates what happened into plain-language flashcards — no extra effort required.

[日本語はこちら](README.ja.md) · [vibeknowledge.dev](https://vibeknowledge.dev) · [MCP Server](#mcp-server)

---

## How it works

```
You build something with Claude Code
         ↓  (PostToolUse hook — zero cost, no claude call)
Events captured to events.jsonl
         ↓  (Stop hook — runs in background via haiku)
"Why did we add a webhook here?" → Plain-language flashcard
         ↓
Open view/index.html → Review cards, quiz yourself, explore concept map
```

| Layer | Role | Cost |
|---|---|---|
| **Capture** (`capture.py`) | Logs Edit/Write/Bash events in real-time | Zero |
| **Distill** (`distill-worker.sh`) | Converts events → cards after each session | Included in Claude subscription by default (switch to a metered API key via `config.json` → `use_api_key`) |
| **Review** (`view/index.html`) | 6-tab viewer: Cards / Projects / Glossary / Concept Map / Quiz / Retrospective | Zero |

- Implementation events with no new concepts → claude is never called (no wasted tokens)
- Distill runs in background — **zero latency added to your sessions**
- Self-recursion safe: the distill process's own events are ignored

---

## Install

```bash
git clone https://github.com/Shown06/vibe-knowledge
cd vibe-knowledge
git checkout v1.1.0   # pin to a released version (see Releases)
bash install.sh
```

That's it. Start building with Claude Code. Cards accumulate automatically.

**View your cards:**

```bash
open view/index.html
```

### What install.sh actually does

| Step | Action | Where |
|---|---|---|
| 1 | Copies `capture.py`, `build_card.py`, `distill.sh`, `distill-worker.sh` | `~/.claude/hooks/vibe-knowledge/` (new files) |
| 2 | Creates the data directory | `~/.claude/vibe-knowledge/data/` (new files: `events.jsonl`, `.cursor`) |
| 3 | Backs up, then edits your Claude Code settings | `~/.claude/settings.json` → adds a `PostToolUse` hook (runs `capture.py`) and a `Stop` hook (runs `distill.sh`). **You are asked `[y/N]` before this step runs**, and shown exactly what will be added. A timestamped backup (`settings.json.bak-vk-<timestamp>`) is made either way. Declining skips only this step — the rest of the install still completes, and you can enable it later (instructions are printed). |
| 4 | Validates the resulting `settings.json` is still valid JSON | — |
| 5 | Optionally builds and registers the MCP server | `claude mcp add vibe-knowledge …` |

Nothing is sent off your machine at any point — capture, distill, and the viewer all run locally.

If you fetch the installer directly instead of cloning (as the [website](https://vibeknowledge.dev) shows), always use a **pinned release tag**, not `main`:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/Shown06/vibe-knowledge/refs/tags/v1.1.0/install.sh)
```

A tag is immutable — the code you run is exactly what's in that [release](https://github.com/Shown06/vibe-knowledge/releases), and won't change under you later. See all releases: https://github.com/Shown06/vibe-knowledge/releases

---

## Features

- **Auto-capture** — hooks into Claude Code, nothing to configure per-project
- **Secret masking** — API keys, tokens, `.env` files are never stored or sent to the AI
- **SM-2 spaced repetition** — built-in quiz with a forgetting curve
- **Concept map** — force-directed graph of how terms connect
- **Project filtering** — cards organized by which project you were building
- **Offline viewer** — pure vanilla HTML/JS, no server needed

---

## Privacy

All data stays on your machine (`~/.claude/vibe-knowledge/data/`).  
The capture hook automatically redacts:

- API keys and tokens (`sk-...`, `ghp_...`, `Bearer ...`, etc.)
- Password/secret key=value pairs
- Full contents of `.env`, `*.key`, `*.pem` files

If you work on client or NDA-covered projects, see **Configuration** below to exclude
them from capture entirely.

---

## Configuration

All optional settings live in `~/.claude/vibe-knowledge/config.json` (created by `install.sh`
with safe defaults; edit it any time — no reinstall needed).

```json
{
  "exclude_paths": [],
  "use_api_key": false
}
```

| Key | Default | What it does |
|---|---|---|
| `exclude_paths` | `[]` | List of path substrings. If a project's working directory matches any entry, `capture.py` returns immediately for that project — nothing is logged, ever. Useful for client/NDA work you don't want turned into flashcards. Example: adding `"/Clients/AcmeCorp"` excludes any project under that path. |
| `use_api_key` | `false` | By default, card generation runs in the background using your **Claude Pro/Max subscription quota** (one `claude -p` call roughly once per turn). Set this to `true` and export `ANTHROPIC_API_KEY` if you'd rather pay per-token on a metered API key instead of spending subscription quota. |

If `config.json` is missing or malformed, both settings fall back to their defaults
(capture stays on for all projects; the subscription is used) — a broken config file
never silently blocks capture.

---

## MCP Server

Expose your knowledge base to Claude Code as a query-able MCP tool.

```bash
cd mcp-server
npm install && npm run build
claude mcp add vibe-knowledge node $(pwd)/dist/index.js
```

Available tools inside Claude Code:

| Tool | What it does |
|---|---|
| `vk_search_cards` | Search your flashcards by keyword or project |
| `vk_get_stats` | Total cards, terms, projects breakdown |
| `vk_grade_term` | Grade a term (0=forgot, 1=hazy, 2=got it) — updates SRS schedule |

Available resources:

| URI | Contents |
|---|---|
| `vibe://cards` | All your flashcards |
| `vibe://terms` | Full glossary with SRS state |

---

## Card format

```json
{
  "term": "Webhook",
  "reading": "ウェブフック",
  "easy": "A way to automatically notify another system when something happens.",
  "why": "Used to notify our server when a Stripe payment completes.",
  "analogy": "Like a doorbell — you press it when something happens, whoever's home responds.",
  "related": ["API", "Event", "Server"],
  "code_ref": "stripe webhook handler"
}
```

---

## Data files

| File | Contents |
|---|---|
| `~/.claude/vibe-knowledge/data/cards.jsonl` | All flashcards (one JSON per line) — **the source of truth** |
| `~/.claude/vibe-knowledge/data/terms.json` | Glossary master with SRS state |
| `~/.claude/vibe-knowledge/data/events.jsonl` | Raw implementation events (grows over time, safe to clear) |
| `~/.claude/vibe-knowledge/data/.cursor` | Cursor: last processed events line |

---

## Website

**[vibeknowledge.dev](https://vibeknowledge.dev)** — project homepage with install instructions and feature overview.

---

## Uninstall

Remove the two hook entries from `~/.claude/settings.json`:

- `PostToolUse` → `capture.py`
- `Stop` → `distill.sh`

A backup was saved at `~/.claude/settings.json.bak-vk-*` when you ran `install.sh`.

---

## License

MIT — see [LICENSE](LICENSE)

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
| **Distill** (`distill-worker.sh`) | Converts events → cards after each session | Included in Claude subscription |
| **Review** (`view/index.html`) | 6-tab viewer: Cards / Projects / Glossary / Concept Map / Quiz / Retrospective | Zero |

- Implementation events with no new concepts → claude is never called (no wasted tokens)
- Distill runs in background — **zero latency added to your sessions**
- Self-recursion safe: the distill process's own events are ignored

---

## Install

```bash
git clone https://github.com/Shown06/vibe-knowledge
cd vibe-knowledge
bash install.sh
```

That's it. Start building with Claude Code. Cards accumulate automatically.

**View your cards:**

```bash
open view/index.html
```

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

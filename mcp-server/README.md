# @vibeknowledge/mcp-server

MCP server for [Vibe Knowledge](https://github.com/Shown06/vibe-knowledge).

Exposes your personal coding flashcard collection to Claude Code.

## Requirements

- Vibe Knowledge installed (`bash install.sh` from the root)
- Node.js 20+

## Install

```bash
# 1. Build
npm install && npm run build

# 2. Add to Claude Code
claude mcp add vibe-knowledge node /path/to/mcp-server/dist/index.js
```

## Tools

| Tool | Description |
|---|---|
| `vk_search_cards` | Search your flashcards by keyword |
| `vk_get_stats` | Get stats: total cards, terms, projects |
| `vk_grade_term` | Grade a term (SRS: 0=forgot, 1=hazy, 2=got it) |

## Resources

| URI | Description |
|---|---|
| `vibe://cards` | All your flashcards |
| `vibe://terms` | Full glossary |

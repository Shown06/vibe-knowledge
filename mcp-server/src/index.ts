#!/usr/bin/env node
/**
 * Vibe Knowledge MCP server.
 *
 * Exposes the user's personal coding flashcard collection (auto-generated from
 * Claude Code sessions) to any MCP client. Reads from the local data directory
 * written by the Vibe Knowledge hooks: ~/.claude/vibe-knowledge/data/
 *
 *   cards.jsonl   one JSON Card per line
 *   terms.json    object keyed by term name -> Term
 *   .cursor       integer cursor of the last translated event line
 */

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListResourcesRequestSchema,
  ListToolsRequestSchema,
  ReadResourceRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import { promises as fs } from "node:fs";
import { homedir } from "node:os";
import path from "node:path";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface Card {
  id: string;
  ts: string;
  project: string;
  term: string;
  reading: string;
  easy: string;
  why: string;
  analogy: string;
  explain?: string;
  qa?: { q: string; a: string }[];
  related: string[];
  code_ref?: string;
}

interface Srs {
  ease: number;
  interval: number;
  due: string;
  reps: number;
}

interface Term {
  reading: string;
  definition?: string;
  analogy?: string;
  first_seen: string;
  last_seen: string;
  count: number;
  related: string[];
  srs?: Srs;
}

type Terms = Record<string, Term>;

// ---------------------------------------------------------------------------
// Paths
// ---------------------------------------------------------------------------

const DATA_DIR = path.join(homedir(), ".claude", "vibe-knowledge", "data");
const CARDS_PATH = path.join(DATA_DIR, "cards.jsonl");
const TERMS_PATH = path.join(DATA_DIR, "terms.json");

const NOT_INSTALLED_MSG =
  "Vibe Knowledge is not installed. Run install.sh first.";

// ---------------------------------------------------------------------------
// Data access (graceful degradation)
// ---------------------------------------------------------------------------

class NotInstalledError extends Error {
  constructor() {
    super(NOT_INSTALLED_MSG);
    this.name = "NotInstalledError";
  }
}

/** Throws NotInstalledError if the data directory is missing. */
async function ensureInstalled(): Promise<void> {
  try {
    const stat = await fs.stat(DATA_DIR);
    if (!stat.isDirectory()) throw new NotInstalledError();
  } catch (err) {
    if (err instanceof NotInstalledError) throw err;
    throw new NotInstalledError();
  }
}

/** Read all cards from cards.jsonl. Malformed lines are skipped. */
async function readCards(): Promise<Card[]> {
  let raw: string;
  try {
    raw = await fs.readFile(CARDS_PATH, "utf8");
  } catch {
    return [];
  }
  const cards: Card[] = [];
  for (const line of raw.split("\n")) {
    const trimmed = line.trim();
    if (!trimmed) continue;
    try {
      cards.push(JSON.parse(trimmed) as Card);
    } catch {
      // Skip malformed line, keep reading the rest.
    }
  }
  return cards;
}

/** Read the term glossary from terms.json. Returns {} on any failure. */
async function readTerms(): Promise<Terms> {
  try {
    const raw = await fs.readFile(TERMS_PATH, "utf8");
    const parsed = JSON.parse(raw);
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
      return parsed as Terms;
    }
    return {};
  } catch {
    return {};
  }
}

/** Atomically write terms.json (temp file + rename). */
async function writeTerms(terms: Terms): Promise<void> {
  const tmp = `${TERMS_PATH}.tmp-${process.pid}`;
  const json = JSON.stringify(terms, null, 2);
  await fs.writeFile(tmp, json, "utf8");
  await fs.rename(tmp, TERMS_PATH);
}

// ---------------------------------------------------------------------------
// Tool logic
// ---------------------------------------------------------------------------

interface SearchArgs {
  query?: unknown;
  project?: unknown;
  limit?: unknown;
}

async function searchCards(args: SearchArgs) {
  const query = typeof args.query === "string" ? args.query : "";
  const project =
    typeof args.project === "string" && args.project.length > 0
      ? args.project
      : undefined;
  const limit =
    typeof args.limit === "number" && Number.isFinite(args.limit)
      ? Math.max(1, Math.floor(args.limit))
      : 20;

  const needle = query.toLowerCase();
  const cards = await readCards();

  const matched = cards.filter((c) => {
    if (project && c.project !== project) return false;
    if (!needle) return true;
    const haystack = [c.term, c.easy, c.why, c.analogy]
      .map((s) => (typeof s === "string" ? s.toLowerCase() : ""))
      .join("\n");
    return haystack.includes(needle);
  });

  return {
    cards: matched.slice(0, limit),
    total: matched.length,
    query,
  };
}

async function getStats() {
  const [cards, terms] = await Promise.all([readCards(), readTerms()]);

  const projectCounts = new Map<string, number>();
  for (const c of cards) {
    const name = typeof c.project === "string" ? c.project : "(unknown)";
    projectCounts.set(name, (projectCounts.get(name) ?? 0) + 1);
  }
  const projects = [...projectCounts.entries()]
    .map(([name, count]) => ({ name, count }))
    .sort((a, b) => b.count - a.count);

  const topTerms = Object.entries(terms)
    .map(([term, t]) => ({ term, count: typeof t.count === "number" ? t.count : 0 }))
    .sort((a, b) => b.count - a.count)
    .slice(0, 20);

  // Latest card timestamp is the best "last updated" signal we have.
  let lastUpdated = "";
  for (const c of cards) {
    if (typeof c.ts === "string" && c.ts > lastUpdated) lastUpdated = c.ts;
  }

  return {
    totalCards: cards.length,
    totalTerms: Object.keys(terms).length,
    projects,
    topTerms,
    lastUpdated,
  };
}

interface GradeArgs {
  term?: unknown;
  grade?: unknown;
}

const EASE_MIN = 0.1;
const EASE_DEFAULT = 2.5;
const INTERVAL_MIN = 1;

function todayISO(): string {
  return new Date().toISOString().slice(0, 10);
}

function addDaysISO(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() + Math.max(0, Math.round(days)));
  return d.toISOString().slice(0, 10);
}

/** Apply an SM-2-style update to an SRS state given a grade. */
function gradeSrs(prev: Srs | undefined, grade: 0 | 1 | 2): Srs {
  let ease = prev && typeof prev.ease === "number" ? prev.ease : EASE_DEFAULT;
  let interval =
    prev && typeof prev.interval === "number" && prev.interval > 0
      ? prev.interval
      : INTERVAL_MIN;
  let reps = prev && typeof prev.reps === "number" ? prev.reps : 0;

  if (grade === 2) {
    // Got it: lengthen interval, bump ease.
    interval = interval * ease;
    ease = ease + 0.05;
    reps = reps + 1;
  } else if (grade === 1) {
    // Hazy: small lengthen, drop ease.
    interval = interval * 1.2;
    ease = ease - 0.05;
    reps = reps + 1;
  } else {
    // Forgot: reset.
    interval = 1;
    reps = 0;
  }

  ease = Math.max(EASE_MIN, ease);
  interval = Math.max(INTERVAL_MIN, interval);

  return {
    ease,
    interval,
    due: addDaysISO(interval),
    reps,
  };
}

async function gradeTerm(args: GradeArgs) {
  const term = typeof args.term === "string" ? args.term : "";
  if (!term) {
    throw new Error("`term` is required and must be a string.");
  }
  const gradeNum = Number(args.grade);
  if (![0, 1, 2].includes(gradeNum)) {
    throw new Error("`grade` must be 0 (forgot), 1 (hazy), or 2 (got it).");
  }
  const grade = gradeNum as 0 | 1 | 2;

  const terms = await readTerms();
  const existing = terms[term];

  if (!existing) {
    throw new Error(
      `Term "${term}" not found in glossary. Use vk_search_cards to find exact term names.`,
    );
  }

  const srs = gradeSrs(existing.srs, grade);
  existing.srs = srs;
  existing.last_seen = todayISO();
  terms[term] = existing;

  await writeTerms(terms);

  const label = grade === 2 ? "got it" : grade === 1 ? "hazy" : "forgot";
  const message =
    grade === 0
      ? `Graded "${term}" as forgot. Reset — review again tomorrow (${srs.due}).`
      : `Graded "${term}" as ${label}. Next review in ${Math.round(
          srs.interval,
        )} day(s) on ${srs.due} (ease ${srs.ease.toFixed(2)}).`;

  return { term, srs, message };
}

// ---------------------------------------------------------------------------
// MCP server wiring
// ---------------------------------------------------------------------------

const server = new Server(
  {
    name: "vibe-knowledge",
    version: "0.1.0",
  },
  {
    capabilities: {
      tools: {},
      resources: {},
    },
  },
);

const TOOLS = [
  {
    name: "vk_search_cards",
    description:
      "Search your Vibe Knowledge flashcards by keyword (case-insensitive substring match over term, easy explanation, why, and analogy). Optionally filter by project.",
    inputSchema: {
      type: "object",
      properties: {
        query: {
          type: "string",
          description: "Keyword to search for (case-insensitive).",
        },
        project: {
          type: "string",
          description: "Optional project name to filter cards by.",
        },
        limit: {
          type: "number",
          description: "Maximum number of cards to return (default 20).",
        },
      },
      required: ["query"],
    },
  },
  {
    name: "vk_get_stats",
    description:
      "Get statistics about your Vibe Knowledge collection: total cards, total terms, per-project counts, top terms by frequency, and last updated timestamp.",
    inputSchema: {
      type: "object",
      properties: {},
    },
  },
  {
    name: "vk_grade_term",
    description:
      "Grade your recall of a term and update its spaced-repetition (SM-2) schedule. Grades: 0 = forgot, 1 = hazy, 2 = got it. Persists to terms.json.",
    inputSchema: {
      type: "object",
      properties: {
        term: {
          type: "string",
          description: "Exact term name to grade (must exist in the glossary).",
        },
        grade: {
          type: "number",
          enum: [0, 1, 2],
          description: "0 = forgot, 1 = hazy, 2 = got it.",
        },
      },
      required: ["term", "grade"],
    },
  },
];

server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: TOOLS,
}));

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: rawArgs } = request.params;
  const args = (rawArgs ?? {}) as Record<string, unknown>;

  try {
    await ensureInstalled();

    let result: unknown;
    switch (name) {
      case "vk_search_cards":
        result = await searchCards(args);
        break;
      case "vk_get_stats":
        result = await getStats();
        break;
      case "vk_grade_term":
        result = await gradeTerm(args);
        break;
      default:
        throw new Error(`Unknown tool: ${name}`);
    }

    return {
      content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
    };
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    return {
      isError: true,
      content: [{ type: "text", text: message }],
    };
  }
});

const RESOURCES = [
  {
    uri: "vibe://cards",
    name: "All flashcards",
    description: "Every Vibe Knowledge flashcard as a JSON array.",
    mimeType: "application/json",
  },
  {
    uri: "vibe://terms",
    name: "Glossary",
    description: "The full term glossary (terms.json) as a JSON object.",
    mimeType: "application/json",
  },
];

server.setRequestHandler(ListResourcesRequestSchema, async () => ({
  resources: RESOURCES,
}));

server.setRequestHandler(ReadResourceRequestSchema, async (request) => {
  const { uri } = request.params;

  await ensureInstalled();

  let payload: unknown;
  switch (uri) {
    case "vibe://cards":
      payload = await readCards();
      break;
    case "vibe://terms":
      payload = await readTerms();
      break;
    default:
      throw new Error(`Unknown resource: ${uri}`);
  }

  return {
    contents: [
      {
        uri,
        mimeType: "application/json",
        text: JSON.stringify(payload, null, 2),
      },
    ],
  };
});

// ---------------------------------------------------------------------------
// Boot
// ---------------------------------------------------------------------------

async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  // Never write to stdout — it is the MCP transport. Log to stderr only.
  process.stderr.write("vibe-knowledge MCP server running on stdio\n");
}

main().catch((err) => {
  process.stderr.write(
    `Fatal error starting vibe-knowledge MCP server: ${
      err instanceof Error ? err.stack ?? err.message : String(err)
    }\n`,
  );
  process.exit(1);
});

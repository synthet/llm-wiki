# Architecture

`llmwiki` treats the wiki as a **claim-centric, provenance-aware knowledge base**
whose Markdown pages are rendered projections of underlying claims. The toolkit
is small and layered so the CLI and MCP server share one implementation.

```
                        ┌─────────────────────────────┐
   wiki/pages/*.md ───▶ │ model.Page / wiki.Wiki        │  parse frontmatter,
                        │  (yamlio: PyYAML | fallback)  │  extract wikilinks
                        └───────────────┬──────────────┘
                                        │
             ┌──────────────────────────┼──────────────────────────┐
             ▼                          ▼                           ▼
    ┌─────────────────┐        ┌─────────────────┐         ┌─────────────────┐
    │ lint (validate) │        │ index (build)   │         │ search (query)  │
    │ structural +    │        │ FTS5 | JSON     │◀────────│ + wikilink      │
    │ provenance rules│        │ + link graph    │         │   expansion     │
    └─────────────────┘        └─────────────────┘         └─────────────────┘
             │                          │                           │
             └──────────────┬───────────┴───────────────┬──────────┘
                            ▼                            ▼
                     ┌────────────┐               ┌──────────────┐
                     │ ops (JSON) │──────────────▶│ cli / mcp     │
                     └────────────┘               │ (same output) │
                                                  └──────────────┘
```

## Modules
| Module | Responsibility |
|---|---|
| `llmwiki.yamlio` | Frontmatter split + YAML load/dump. PyYAML when present, else a stdlib subset parser (handles block scalars, nested maps, flow collections). |
| `llmwiki.model` | `Page` dataclass, controlled vocabularies, wikilink extraction, Markdown stripping, `PageIssue`. |
| `llmwiki.wiki` | `Wiki` collection: discovery, loading, name/id resolution, backlink/outbound graph. |
| `llmwiki.lint` | Structural + semantic rules → `PageIssue` list. |
| `llmwiki.index` | Build/query the index. SQLite FTS5 (BM25) with a JSON inverted-index fallback; stores the wikilink graph. |
| `llmwiki.search` | Index query + optional one-hop wikilink expansion. |
| `llmwiki.ops` | High-level operations returning plain JSON — the shared core. |
| `llmwiki.cli` | `argparse` CLI (`llmwiki ...`). |
| `llmwiki.mcp_server` | Dependency-free JSON-RPC MCP server over stdio. |

## Design principles (from the research baseline)
- **Raw evidence is immutable; synthesis is replaceable.** Sources are
  content-addressed (`sha256:`); pages can be rebuilt from claims.
- **Review status is data**, with explicit machine-readable states.
- **Provenance descends below page level** — evidence attaches to atomic claims.
- **The LLM proposes; schema constrains; evidence grounds; humans authorize.**
- **Format interoperability over lock-in** — the internal model is richer than
  any single export (see the roadmap in `README.md` for OKF/RO-Crate/DCAT).

## Why two back-ends
FTS5 gives fast BM25 ranking and snippets where SQLite is built with it (the
common case). Environments without FTS5 still work via a pure-Python BM25 over a
JSON inverted index. Both expose the same `SearchResult`, so nothing downstream
changes.

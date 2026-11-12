# CLAUDE.md

Guidance for Claude Code (and other agents) working in this repository.

## What this project is

Regteia turns Brazilian financial regulation (BCB, CMN, CVM, and the federal laws they rest on) into a
**queryable graph**: which norm revokes, amends, cites or regulates which, down to the article, and what was in
force on a given date.

It is **local-first**: a Docker Compose stack on the owner's machine (Neo4j, an hourly updater, and a local web
app with the graph visualization and corpus statistics), plus a **local-only MCP server** that AI clients on the
same machine launch over stdio. Nothing is hosted or exposed to the network.

We do **not** crawl the official portals ourselves (yet). We ingest the public corpora maintained upstream and add
the layers they don't have: article-level amendments, point-in-time validity, multi-hop traversal, body-text
citations and federal-law text.

## Architecture: hard boundaries

```
                         ┌──────────── docker compose (always on, 127.0.0.1 only) ────────────┐
upstream git repos ──►   │  updater (ingest, hourly) ──► Neo4j ──► server (web + stats + API) │ ──► browser
                         └──────────────────────────────────┬─────────────────────────────────┘
                                                            │ read-only
                         AI client (Claude Code/Desktop) ──► regteia-mcp (stdio, launched on demand)
```

These rules are the point of the architecture. Do not break them without an explicit decision recorded in
`docs/decisions/`.

1. **`ingest` is the only package that writes to Neo4j.** It also owns migrations.
2. **`query` holds all read logic.** `mcp`, `server` and the CLI are thin adapters: argument parsing and
   formatting only. If you are writing Cypher or business rules outside `ingest` or `query`, move it.
3. **Packages depend only on `schema`, never on each other** (exception: `mcp` and `server` depend on `query`).
   `mcp` and `server` never import `ingest`.
4. **The MCP is local and read-only.** stdio transport only; no HTTP listener. It exposes fixed, parameterized
   queries from `query`, run in read transactions. No "run Cypher" tool, no write tools. Neo4j Community Edition has
   no RBAC, so read-only access is enforced in code, not by the database.
5. **Nothing listens beyond localhost.** Every port in `docker-compose.yml` is bound to `127.0.0.1`.
6. **The pipeline is deterministic.** No LLM calls in `ingest` or `query`. Parsing is regex + rules, and every
   derived edge records where it came from (`fonte`).
7. **Neo4j is derived, never the source of truth.** It must be fully rebuildable with `regteia-ingest full`.

## Repository layout

```
packages/
  schema/   regteia-schema   Pydantic v2 models, ID helpers, enums. The shared contract.
  ingest/   regteia-ingest   sources/ (upstream adapters), parse/, load/ (Neo4j writer), migrations, CLI
  query/    regteia-query    read-only functions: buscar, norma, relacoes, vigencia_em, panorama, estatisticas,
                             exportar_grafo. Also ships the `regteia` CLI (thin wrapper, for debugging and agents)
  mcp/      regteia-mcp      MCP server over stdio, wraps query
  server/   regteia-server   FastAPI: JSON API + graph export (Apache Arrow) + serves the built web app
apps/
  web/                       Vite + TypeScript: overview (cosmos.gl), stats dashboard, per-norm page (Cytoscape.js)
db/
  migrations/                NNN_description.cypher, applied in order by `regteia-ingest migrate`
docker-compose.yml           neo4j, updater, server. All ports on 127.0.0.1. Volumes: neo4j-data, upstream
upstreams.toml               the upstream repos to ingest (url, ref, adapter). Single place they are named
docs/
  graph-model.md             node/edge reference (keep in sync with schema + migrations)
  decisions/                 short ADRs for anything that changes the boundaries above
tests/fixtures/              ~20 real upstream norm files (incl. Res. BCB 520 and 589) + graph excerpts
_upstream/                   upstream clones when ingest runs outside Docker (gitignored)
```

## Commands

```bash
cp .env.example .env                       # NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD
docker compose up -d                       # neo4j (:7474 browser, :7687 bolt), updater, server (:8080)
docker compose logs -f updater             # watch hourly ingests

# development, outside containers
uv sync --all-packages
uv run regteia-ingest migrate              # apply db/migrations
uv run regteia-ingest full                 # clone upstream, load everything (first run)
uv run regteia-ingest incremental          # load only files changed since the last ingested SHA
uv run regteia norma "Resolução BCB 520"   # query CLI
uv run regteia vigencia "bcb:resolucao-bcb:520#art-88" 2027-01-02
uv run regteia-mcp                         # MCP over stdio (normally launched by the AI client, not by hand)
uv run regteia-server --reload             # API + web on http://127.0.0.1:8080
cd apps/web && npm install && npm run dev  # frontend dev server, proxies /api to :8080

uv run pytest                              # unit + integration (testcontainers starts Neo4j)
uv run pytest -m "not integration"         # fast, no Docker
uv run ruff check . && uv run ruff format --check .
```

Status: the repository is being scaffolded. If a command above doesn't exist yet, create it as described rather
than inventing a different interface.

## Scheduling

GitHub Actions cannot reach the local database, so it runs **CI only** (`ci.yml`: ruff + pytest). Hourly updates
run in the `updater` compose service, a loop calling `regteia-ingest incremental` and then sleeping for an hour.
Because incremental ingest diffs from the last loaded upstream SHA, missed hours (laptop asleep) are caught up on
the next run. Upstream publishes at minute 41 of each hour; exact timing doesn't matter.

## Upstream data (read before touching `ingest/sources/`)

| Repo | What | License |
|---|---|---|
| `github.com/BrunooMoniz/normas-bcb` | 60,977 BCB/CMN norms, updated hourly | code MIT, texts are official acts |
| `github.com/BrunooMoniz/normas-cvm` | 2,606 CVM norms | code MIT, texts are official acts |
| `github.com/ctresb/leis` | federal laws the BCB/CVM norms rest on (planned, roadmap step 9) | code MIT, texts are official acts |

Counts as of 2026-11-11. Upstream is maintained by one person and has no published schema, so **validate every
record against `schema` and fail loudly on mismatch**. Never silently skip.

**Upstreams are declared in `upstreams.toml`, never as git submodules.** Each entry has `name`, `url` (a git URL
or a local path), `ref` (branch, tag or commit SHA to pin), `adapter`, `acervo`, plus optional `sparse` and
`enabled`. Both normas repos use the same adapter (`normas_grafo`): upstream's `grafo.py` is identical in both.
ctresb/leis uses the `ctresb_leis` adapter, which checks out only the files referenced by the graph (see below).

Clones live in `$REGTEIA_UPSTREAM_DIR/<name>`: the `upstream` Docker volume in compose (`/data/upstream`), or
`./_upstream/` (gitignored) when run outside Docker. Never inside the repo's tracked tree. Per upstream, each run:

1. Blobless clone on the first run (`--filter=blob:none`, plus sparse checkout if configured).
2. `git fetch`, then `git checkout --detach <ref>`; the resolved commit is `new_sha`.
3. Read `last_sha` from `(:Ingestao {fonte: name})`. No `last_sha`: full load. Equal: skip. Otherwise
   `git diff --name-status last_sha..new_sha` → upsert changed norms and `grafo/` files, delete removed ones.
   `last_sha` missing from history (force push): full reload.
4. Only after a successful load, set `(:Ingestao {fonte, sha: new_sha, em, arquivos})`. Failed runs retry next hour.

Every `Norma` stores `caminho` and `upstream_sha`, so outputs can link to the exact file version:
`<url without .git>/blob/<upstream_sha>/<caminho>`. The official link (`fonte_url`) always comes first.

Per norm: one Markdown file with a frontmatter block. Each frontmatter line is `key: value`, where the value is
JSON when it starts with `"` or `[`, otherwise raw (e.g. `data: 2025-11-10`, `revogada: false`). Parse it line by
line like upstream does; don't assume arbitrary YAML.

- Always present: `titulo, orgao, tipo, numero, data, revogada, versao_texto, fonte, baixado_em`
- Sometimes: `ementa, responsavel, versao_normativo, publicacao, atualizacoes, normas_vinculadas, referencias`
- From PDF: `arquivo, sha256_arquivo`, plus `ocr: true` when OCR was used (treat OCR text as lower confidence)

Graph files in each repo's `grafo/` folder:

```jsonc
// estado.jsonl
{"id":"bcb:resolucao-bcb:520","caminho":"resolucoes-bcb/2025/resolucao-bcb-0520.md","estado":"vigente","por":[]}
// arestas.jsonl. relacao ∈ revoga | revoga_parcial | altera | cita | regulamenta | conjunta
{"de":"bcb:carta-circular:1","para":"bcb:resolucao-cmn:47","relacao":"cita","desde":null,"fonte":"referencias"}
// externos.jsonl: norms that live in another repo or in ctresb/leis
{"id":"bcb:circular:1667","url":"https://github.com/BrunooMoniz/normas-bcb/blob/main/circulares/1990/circular-1667.md"}
// nao_resolvidos.jsonl: references upstream could not resolve (3,509 total), a backlog we want to shrink
{"id":"bcb:carta-circular:11283","arestas":1,"em":"bcb:circular:925","campo":"normas_vinculadas"}
```

`estado` ∈ `vigente | alterada | revogada`. `fonte` is the upstream field the edge came from, sometimes joined
with `+` (e.g. `atualizacoes+referencias`).

**IDs: reuse upstream IDs as primary keys.** Examples: `bcb:resolucao-bcb:520`, `cvm:instrucao:68`,
`lei:4595-1964`, `dec:60190-1967`. Federal prefixes: `lei, lcp, ldl, del, dec, mpv`; `ext:` is used for other
external references. A LexML URN may be stored as an extra `urn` property but is never the key.

### ctresb/leis (federal laws)

Same Markdown + frontmatter format, plus a `urn` (LexML) field and `fonte` on normas.leg.br. Example path:
`federal/leis-ordinarias/2022/lei-14478-2022-12-21.md`. Rules:

- **It is huge (~1.49M files): federal, state and municipal laws, other regulators, treaties.** Never check out
  whole folders. Ingest only the laws that BCB/CVM edges point to (`lei, lcp, ldl, del, dec, mpv` IDs in
  `arestas.jsonl` / `externos.jsonl`), resolved to paths in these folders: `federal/leis-ordinarias`,
  `leis-complementares`, `leis-delegadas`, `decretos-lei`, `decretos`, `medidas-provisorias`. Ignore folders
  starting with `_` (they are the maintainer's work in progress).
- **`versao_texto` varies:** `"compilada (texto vigente)"` (consolidated current text, e.g. Lei 4.595/1964) or
  `"original"` (as first published, e.g. Lei 14.478/2022). Store it, and surface it in every answer that quotes a
  law. Never present `original` text as current wording.
- It updates irregularly (days apart), not hourly.

## Graph model (v1). Full reference in docs/graph-model.md

```
(:Norma {id, acervo, orgao, tipo, numero, data, titulo, ementa, estado, fonte_url, caminho,
         upstream_sha, ocr})
(:Dispositivo {id, rotulo, texto, ordem})       // id: "bcb:resolucao-bcb:520#art-88", "...#anexo-i/art-2"
(:Ingestao {fonte, sha, em, arquivos})

(:Norma)-[:TEM_DISPOSITIVO]->(:Dispositivo)
(:Norma)-[:REVOGA|REVOGA_PARCIAL|ALTERA|CITA|REGULAMENTA|CONJUNTA {desde, fonte}]->(:Norma)
(:Norma)-[:ALTERA {a_partir_de, tipo, fonte:"atualizacoes"}]->(:Dispositivo)   // tipo: nova_redacao|inclusao|revogacao
(:Dispositivo)-[:CITA {fonte:"texto"}]->(:Norma)
```

- Relationship types are the upstream `relacao` values in upper case. Don't invent synonyms.
- Writes are idempotent `MERGE` in batches (`UNWIND $rows`). Re-running ingest must not duplicate anything.
- Required indexes (in migrations): unique `Norma.id` and `Dispositivo.id`; full-text index over
  `Dispositivo.texto`, `Norma.titulo` and `Norma.ementa` with the Portuguese (`brazilian`) analyzer.

### The `atualizacoes` parser (our main value-add)

Upstream lists article-level amendments as structured text, e.g.

```
Resolução BCB nº 589/2026 - Alteração, a partir de 1º/1/2027 - Nova redação: art. 88, inciso III,
alíneas "b", "c", "d" e "e". Inclusão: arts. 90-A e 90-B.
```

Parse each entry into `ALTERA` edges from the amending norm to the affected `Dispositivo`s, with `a_partir_de` and
`tipo`. **Effective dates can be in the future** (the example takes effect in 2027), so never assume an amendment
already applies. Every entry that fails to parse goes to a report (shown on the stats page); never drop entries
silently. Test cases for this parser must come from real upstream strings.

## Web app (`apps/web`, served by `server`)

- **Overview:** the whole graph in cosmos.gl (GPU force layout), colored by issuing body (CMN, BCB, CVM, federal
  law), with filters by body, relation type and decade. Data comes from `GET /api/grafo.arrow`
  (`query.exportar_grafo`), cached until the next ingest.
- **Stats dashboard:** coverage and health of the corpus, all computed live from Neo4j by `query.estatisticas`:
  norms per series and body, vigente/alterada/revogada counts, edges by relation and by `fonte`, norms per decade,
  unresolved references, `atualizacoes` parse failures, last ingest (upstream SHA, time, files changed). The same
  numbers can be exported as SVG for the README.
- **Norm page:** text by article, amendment timeline, "in force on [date]" switch, and a neighborhood graph (norm +
  1–2 hops) in Cytoscape.js + `cytoscape-dagre`, laid out left to right by date.

## Domain rules (correctness over convenience)

- **Never present a revoked norm or provision as in force.** Every answer from `query` carries `estado` and
  `fonte_url` (the official source link).
- `estado = "alterada"` means the stored text is the portal's current consolidated text. Say so.
- **Known limit:** we have status over time, but not text over time. We only have the text as currently published
  (plus upstream's git history since late 2026). `vigencia_em` can say *whether* an article applied on a date. It
  cannot return the article's *wording* on that date unless we have that version. Never make up historical text.
- Comunicados (≈44k of the BCB items) are mostly auction notices. Down-rank them in search by default and keep them
  out of the overview graph unless a filter includes them; don't delete them.
- Every user-facing output repeats the disclaimer: automated conversion, informational only; it does not replace
  the Diário Oficial or the BCB/CVM portals.

## Conventions

- Python 3.12+, uv workspace, Pydantic v2, official `neo4j` driver, official `mcp` SDK, FastAPI, pytest, ruff.
  Frontend: Vite + TypeScript, `@cosmos.gl/graph`, `cytoscape` + `cytoscape-dagre`, `apache-arrow`.
- **Naming:** domain vocabulary stays in Portuguese (`norma`, `dispositivo`, `vigente`, `revoga`, `altera`,
  `vigencia_em`, `estatisticas`) because that's how the source material and users speak. Everything else
  (infrastructure, helpers, docs) is in English.
- Cypher lives in `.cypher` files next to the code that runs it (`query/queries/`, `ingest/load/`), loaded at import
  time, always parameterized. No f-string Cypher.
- Config comes only from environment variables (`.env` for local dev). No secrets in code or fixtures.
- Integration tests use testcontainers with a real Neo4j. No mocked database for query tests.

## Do not

- Commit upstream data, Neo4j dumps or generated binaries to this repo.
- Bind any port to `0.0.0.0`, add an HTTP transport to the MCP, or add deployment/hosting config.
- Add an LLM call anywhere in the data path.
- Give the MCP a "run Cypher" tool or any write capability.
- Add embeddings / a vector index before keyword search + graph traversal are shown to be insufficient (record
  that decision in `docs/decisions/` first).
- Change upstream IDs or relation names.

## Roadmap

1. Scaffold: uv workspace, `docker-compose.yml` (neo4j + updater + server), migrations, CI.
2. Norm-level graph from upstream (`estado`, `arestas`, `externos`, frontmatter) with incremental ingest.
3. `query` + `regteia` CLI + stats (`estatisticas`).
4. Web: stats dashboard and cosmos.gl overview.
5. Split norms into `Dispositivo`s, plus the full-text index; `buscar`.
6. Local MCP (stdio): `buscar`, `norma`, `relacoes`, `panorama`.
7. `atualizacoes` parser → article-level `ALTERA` + `vigencia_em`; norm page with timeline and neighborhood graph.
8. Body-text citation extractor; shrink `nao_resolvidos`.
9. Federal laws from ctresb/leis as real nodes with text.
10. Optional: own crawler as another adapter in `ingest/sources/`; embeddings if justified.
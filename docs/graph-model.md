# Graph model

Keep in sync with `packages/schema` and `db/migrations`. Status: roadmap step 2 (norm level). `Dispositivo` and
article-level `ALTERA` arrive in steps 5 and 7.

## Nodes

### `(:Norma)`

One node per norm ID (upstream IDs, unique constraint `norma_id`). Two kinds, told apart by `externo`:

**File-backed** (`externo: false`): a norm with a Markdown file in normas-bcb or normas-cvm.

| Property | From | Notes |
|---|---|---|
| `id` | `grafo/estado.jsonl` | e.g. `bcb:resolucao-bcb:520`, `cvm:instrucao:68` |
| `acervo` | `upstreams.toml` | `bcb` or `cvm` |
| `estado` | `grafo/estado.jsonl` | `vigente` \| `alterada` \| `revogada`. **Authoritative** |
| `caminho`, `upstream`, `upstream_sha` | ingest | which file, from which repo, at which commit |
| `url_arquivo` | ingest | `<url>/blob/<upstream_sha>/<caminho>`: the exact file version (http(s) upstreams only) |
| `fonte_url` | frontmatter `fonte` | official source; always shown first |
| `orgao, tipo, numero, data, titulo, ementa` | frontmatter | `data` is a Neo4j `Date`; empty `ementa` stored as null |
| `revogada` | frontmatter | upstream's own flag; may disagree with `estado`, which wins |
| `cancelada` | frontmatter | BCB only (161 norms) |
| `versao_texto, publicacao, responsavel, baixado_em, arquivo` | frontmatter | `arquivo`: source PDF, if any |
| `ocr` | frontmatter | `true` = text came from OCR; lower confidence |
| `temas` | frontmatter | CVM only |
| `url_externa` | `grafo/externos.jsonl` | set when another repo lists this norm as external |

**Stub** (`externo: true`): an edge endpoint with no file in our corpora: federal laws (`lei, lcp, ldl, del, dec,
mpv`), other bodies (`ext`), and IDs upstream emitted but could not match to a file. Properties: `id`, `acervo`
(the ID prefix), and `url_externa` when upstream knows where it lives. A stub becomes file-backed when its corpus is
ingested (e.g. federal laws in step 9); a file-backed norm whose file disappears upstream is turned back into a stub
(its edges stay). Stubs nothing points to are deleted.

### `(:NaoResolvido)`

`grafo/nao_resolvidos.jsonl`, replaced as a whole on every graph reload. `upstream`, `em` (the norm where the
reference appears), `campo` (frontmatter field), and `tipo`:

- `alvo`: the reference was parsed into `id` but no such norm exists (`arestas` = edges pointing at it).
- `padrao`: the pattern could not be parsed at all (`padrao`, `exemplo`, `trechos` = occurrences).

### `(:Ingestao {fonte, sha, em, arquivos, modo})`

One per upstream. `sha` is the last *successfully* loaded commit; the next incremental run diffs from it.

### `(:Migracao {nome, em})`

Applied files from `db/migrations`.

## Relationships

`(:Norma)-[:REVOGA|REVOGA_PARCIAL|ALTERA|CITA|REGULAMENTA|CONJUNTA]->(:Norma)` from `grafo/arestas.jsonl`. The type
is upstream's `relacao` in upper case.

| Property | Notes |
|---|---|
| `desde` | `Date` or null. Only ~10% of edges have it (BCB 7,110 / 69,332; CVM 2 / 2,866) |
| `fonte` | upstream field(s) it came from, `+`-joined: `referencias, atualizacoes, normas_vinculadas, numero, notas, revogada_por` |
| `upstream` | which repo emitted it. Part of the key: `(de, para, type, upstream)` |
| `ingestao` | id of the run that last wrote it; edges not rewritten by a graph reload are deleted |

## Indexes (db/migrations)

- Unique: `Norma.id`, `Dispositivo.id`, `Ingestao.fonte`, `Migracao.nome`.
- Range: `Norma.upstream`, `Norma.externo`, `Norma.estado`, `Norma.tipo`, `NaoResolvido.upstream`.
- Full-text `busca_pt` over `Norma|Dispositivo` × `titulo, ementa, texto`, `brazilian` analyzer.

## Counts after the first load (2026-11-11, normas-bcb@39a59edc, normas-cvm@7d8ffce9)

63,583 file-backed norms (48,768 vigente, 594 alterada, 14,221 revogada), 3,005 stubs, 72,198 edges (CITA 29,117,
REGULAMENTA 18,899, REVOGA 15,611, ALTERA 6,430, REVOGA_PARCIAL 2,113, CONJUNTA 28), 3,509 `NaoResolvido`.

# Graph model

Keep in sync with `packages/schema` and `db/migrations`. Status: roadmap step 9 (norms, Dispositivos, article-level
amendments read from `atualizacoes`, `vigencia_em` over them ([ADR 0003](decisions/0003-vigencia-em.md)), the norm
page, citations read from article text ([ADR 0004](decisions/0004-citacoes-no-texto.md)), and the federal acts they
point to, from ctresb/leis ([ADR 0005](decisions/0005-atos-federais.md))).

## Nodes

### `(:Norma)`

One node per norm ID (upstream IDs, unique constraint `norma_id`). Two kinds, told apart by `externo`:

**File-backed** (`externo: false`): a norm with a Markdown file in normas-bcb or normas-cvm, or a federal act with one
in ctresb/leis (ADR 0005; those differ as noted).

| Property | From | Notes |
|---|---|---|
| `id` | `grafo/estado.jsonl` | e.g. `bcb:resolucao-bcb:520`, `cvm:instrucao:68` |
| `acervo` | `upstreams.toml` | `bcb` or `cvm`; for federal acts the ID prefix (`lei`, `dec`, `mpv`…) |
| `estado` | `grafo/estado.jsonl` | `vigente` \| `alterada` \| `revogada`. **Authoritative**. Federal acts: from the frontmatter (ADR 0005), plus `sem_informacao` when the source doesn't say; never shown as in force |
| `estado_motivo` | frontmatter | federal acts: why the source says it's not in force (`Reeditada`, `Convertida em Lei`, `sem vigência segundo os metadados de normas.leg.br`) |
| `urn` | frontmatter | federal acts: LexML URN (never the key) |
| `estado_por` | `grafo/estado.jsonl` `por` | ids of the norms that revoked or amended it, per upstream; absent when none |
| `caminho`, `upstream`, `upstream_sha` | ingest | which file, from which repo, at which commit |
| `url_arquivo` | ingest | `<url>/blob/<upstream_sha>/<caminho>`: the exact file version (http(s) upstreams only) |
| `fonte_url` | frontmatter `fonte` | official source; always shown first |
| `orgao, tipo, numero, data, titulo, ementa` | frontmatter | `data` is a Neo4j `Date`; empty `ementa` stored as null |
| `revogada` | frontmatter | upstream's own flag; may disagree with `estado`, which wins. Null for federal acts whose source doesn't say |
| `cancelada` | frontmatter | BCB only (161 norms) |
| `versao_texto, publicacao, responsavel, baixado_em, arquivo` | frontmatter | `arquivo`: source PDF, if any |
| `ocr` | frontmatter | `true` = text came from OCR; lower confidence |
| `temas` | frontmatter | CVM only |
| `url_externa` | `grafo/externos.jsonl` | set when another repo lists this norm as external |
| `divisao` | ingest | how the body was split: `artigos` \| `itens` \| `texto` \| `vazio` (no text on the portal) |

**Stub** (`externo: true`): an edge endpoint with no file in our corpora: federal laws (`lei, lcp, ldl, del, dec,
mpv`), other bodies (`ext`), and IDs upstream emitted but could not match to a file. Properties: `id`, `acervo`
(the ID prefix), and `url_externa` when upstream knows where it lives. A stub becomes file-backed when its corpus is
ingested (federal acts the BCB/CVM corpora point to, when ctresb/leis has their file); a file-backed norm whose file disappears upstream is turned back into a stub
(its edges stay). Stubs nothing points to are deleted.

### `(:Dispositivo)`

A unit of a file-backed norm's text, built by `ingest/parse/dispositivos.py` at article granularity
([ADR 0001](decisions/0001-dispositivos-por-artigo.md)). Unique constraint `dispositivo_id`.

| Property | Notes |
|---|---|
| `id` | `<norma>#<chave>`: `#preambulo`, `#art-88`, `#art-90-a`, `#anexo-i`, `#anexo-i/art-2`, `#anexo` (unnumbered), `#item-iii`, `#texto` |
| `tipo` | `preambulo` \| `artigo` \| `item` \| `anexo` \| `texto` (a norm with no recognizable structure: its whole body) |
| `rotulo` | `Art. 88`, `Anexo I, art. 2`, `Item III`, `Preâmbulo`, `Texto` |
| `ordem` | position in the norm, from 0 |
| `texto` | latest published wording, Markdown, struck-through parts removed. May include changes with a future effective date (the portal marks them "Redação dada, a partir de …") |
| `numero`, `anexo` | `"90-A"`, `"III"`; annex number for annexes and their articles (`""` if unnumbered) |
| `contexto` | enclosing headings: `CAPÍTULO II · DAS DEFINIÇÕES › Seção I · …` |
| `revogado` | the article only exists struck through, or reads just "(Revogado…)" |
| `redacoes_anteriores` | list of struck-through (superseded) wording, in document order; absent when none |
| `cita_sem_alvo` | BCB/CVM IDs its text cites that match no norm yet (ADR 0004); linked at the end of every run once the norm exists; absent when none |
| `ingestao` | id of the run that last wrote it; a re-split norm loses the Dispositivos that run did not write |

A norm turned back into a stub loses its Dispositivos.

### `(:NaoResolvido)`

`grafo/nao_resolvidos.jsonl`, replaced as a whole on every graph reload. `upstream`, `em` (the norm where the
reference appears), `campo` (frontmatter field), and `tipo`:

- `alvo`: the reference was parsed into `id` but no such norm exists (`arestas` = edges pointing at it).
- `padrao`: the pattern could not be parsed at all (`padrao`, `exemplo`, `trechos` = occurrences).

### `(:Atualizacao)`

One per entry of a norm's `atualizacoes` frontmatter list, in upstream's order (ADR 0002). Replaced whole whenever the
norm is read again. `id` `<norma>#atualizacao-<ordem>`.

| Property | Notes |
|---|---|
| `norma`, `ordem` | the amended norm and the entry's position in its list |
| `texto` | the entry as upstream wrote it |
| `de` | the amending norm (upstream ID, read with upstream's own rules); null for notes and unreadable entries |
| `resultado` | `dispositivos` (every target matched), `parcial`, `ausente` (read, but no target is among the norm's Dispositivos), `norma` (whole-norm event: total revocation, no detail, a consolidated manual), `nota` (an observation, or about another norm), `falha` |
| `motivo` | why, for everything but `dispositivos`; for `falha`/`parcial`, the clause that could not be read |
| `ausentes`, `ausentes_tipo`, `ausentes_desde`, `ausentes_detalhe` | parallel lists: targets that matched no Dispositivo (`art-90-a`), their type, start date and detail (`""` if none) |

### `(:Ingestao {fonte, sha, em, arquivos, modo, divisao, atualizacoes, citacoes})`

One per upstream. `sha` is the last *successfully* loaded commit; the next incremental run diffs from it. `divisao`
is the splitter version (`dispositivos.VERSAO`) that built the Dispositivos, `atualizacoes` the parser version
(`atualizacoes.VERSAO`), `citacoes` the body-text citation extractor version (`citacoes_texto.VERSAO`); a different
version of any of them forces a full reload.

### `(:Migracao {nome, em})`

Applied files from `db/migrations`.

## Relationships

`(:Norma)-[:TEM_DISPOSITIVO]->(:Dispositivo)` and `(:Norma)-[:TEM_ATUALIZACAO]->(:Atualizacao)`: no properties.

`(:Norma)-[:ALTERA {fonte: "atualizacoes"}]->(:Dispositivo)`: the article-level amendments, from the amended
norm's `atualizacoes` (ADR 0002). The amending norm gets a stub if it is outside the corpora.

| Property | Notes |
|---|---|
| `tipo` | `nova_redacao`, `inclusao` or `revogacao` |
| `a_partir_de` | `Date` or null. Can be in the future. Null: the entry gives no date (in force from the amending norm's own date) |
| `detalhe` | what inside the article, as written: `inciso III, alíneas "b", "c"`, `caput; §§ 2º a 4º` |
| `entrada` | `ordem` of the `Atualizacao` it came from |

`(:Dispositivo)-[:CITA {fonte: "texto", ordem}]->(:Norma)`: a norm named in the Dispositivo's text (latest wording,
without the portal's amendment notes), read by `ingest/parse/citacoes_texto.py` (ADR 0004). `ordem` is the order of
first mention (1000 for one linked later, when its norm appeared). A cited federal law or `ext:` norm gets a stub; a
BCB/CVM ID with no norm gets no node and waits in `cita_sem_alvo`. Rebuilt with the norm's Dispositivos.

`(:Norma)-[:REVOGA|REVOGA_PARCIAL|ALTERA|CITA|REGULAMENTA|CONJUNTA]->(:Norma)` from `grafo/arestas.jsonl`. The type
is upstream's `relacao` in upper case.

| Property | Notes |
|---|---|
| `desde` | `Date` or null. Only ~10% of edges have it (BCB 7,110 / 69,332; CVM 2 / 2,866) |
| `fonte` | upstream field(s) it came from, `+`-joined: `referencias, atualizacoes, normas_vinculadas, numero, notas, revogada_por` |
| `upstream` | which repo emitted it. Part of the key: `(de, para, type, upstream)` |
| `ingestao` | id of the run that last wrote it; edges not rewritten by a graph reload are deleted |

## Indexes (db/migrations)

- Unique: `Norma.id`, `Dispositivo.id`, `Atualizacao.id`, `Ingestao.fonte`, `Migracao.nome`.
- Range: `Norma.upstream`, `Norma.externo`, `Norma.estado`, `Norma.tipo`, `NaoResolvido.upstream`,
  `Atualizacao.resultado`, `Atualizacao.de`.
- Full-text `busca_pt` over `Norma|Dispositivo` × `titulo, ementa, texto`, `brazilian` analyzer. `buscar` groups
  Dispositivo hits by norm.

## Counts after the first load (2026-11-11, normas-bcb@39a59edc, normas-cvm@7d8ffce9)

63,583 file-backed norms (48,768 vigente, 594 alterada, 14,221 revogada), 3,005 stubs, 72,198 edges (CITA 29,117,
REGULAMENTA 18,899, REVOGA 15,611, ALTERA 6,430, REVOGA_PARCIAL 2,113, CONJUNTA 28), 3,509 `NaoResolvido`.


Dispositivos (2026-11-12, normas-bcb@9e353a7b, normas-cvm@4a394582): 175,576 (artigo 67,193, texto 42,923, item
42,647, preambulo 20,619, anexo 2,194); 256 revoked, 2,278 with earlier wording. Norms by `divisao`: texto 42,904,
itens 11,133, artigos 9,512, vazio 36.

`atualizacoes` (2026-11-18, normas-bcb@39a59edc; the CVM corpus has none): 18,860 entries (norma 13,642,
dispositivos 3,935, ausente 819, parcial 293, nota 57, falha 114) and 10,301 article-level `ALTERA` edges (nova_redacao
5,461, revogacao 2,879, inclusao 1,961), 3,625 with a start date, 69 starting after the load date.

Citations in article text (2026-11-19, normas-bcb@808e7ca7, normas-cvm@d3972fbd): 157,786 edges from 80,003
Dispositivos (corpus norms 111,961, federal laws 41,809, other bodies 3,967, BCB/CVM stubs 49); 137,834 norm pairs,
80,772 of them with no norm-level edge upstream; 392 waiting in `cita_sem_alvo`. Stubs went from 3,005 to 4,251,
mostly federal laws (step 9 turns them into real nodes).

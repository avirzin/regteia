# 0005. Federal acts from ctresb/leis

Date: 2026-11-19. Status: accepted. Roadmap step 9.

## Context

BCB/CVM norms rest on federal acts (laws, decrees, provisional measures). Until now these were stubs named from
their ID. ctresb/leis has them as Markdown with frontmatter, but it is huge (~1.49M files: federal, state and
municipal acts, other regulators, treaties) and has no graph of its own.

Measured (ctresb/leis@c9f21b4a, 2026-11-02; our graph on 2026-11-19):

- 1,945 federal IDs are referenced by the BCB/CVM corpora; 1,622 have a file (83%), carrying 63,609 of the 64,262
  edges and citations into federal acts (99%). Most of the rest are wrong IDs upstream (`lei:2291-1986` is
  Decreto-Lei 2.291; `lei:6404-7613`), MPs cited without their reissue number, and decrees ctresb/leis lacks.
- A shallow, blobless clone is 45 MB and 10 s. Checking out the referenced files adds 43 MB and ~30 s.
- `versao_texto`: 1,143 `original` (the act as published), 432 `compilada` (current consolidated text),
  45 `republicação/retificação`, 2 other.
- Status: `revogada` is `true` for 152, `false` for 1,084 and `null` for 386 (mostly decrees). 121 MPs say
  `situacao: "Reeditada"`, `"Reeditada com alteração"` or `"Convertida em Lei"` with `revogada: false`. 165 decrees
  say `forca_legal_fonte: ["NotInForce"]` (from normas.leg.br metadata) with `revogada: null`.

## Decision

1. **Load only what the graph points to.** The `ctresb_leis` adapter reads from the graph which federal acts the
   BCB/CVM corpora reference (an edge with a BCB/CVM norm, a citation in a BCB/CVM Dispositivo, or an
   article-level amendment), resolves them to paths from the trees (`git ls-tree`, no file content), and checks out
   only those files (sparse checkout). Citations in federal acts' own text don't count, or every law would pull in
   the laws it cites. An act no longer referenced goes back to a stub. The upstream runs after the normas repos.
2. **Shallow.** The clone keeps only the latest commit, so there is no diff: when the commit changes, every loaded
   act is read again (~1,600 files, ~15 s). When it doesn't, only newly referenced acts are read.
3. **IDs stay upstream's.** `federal/<folder>/<year>/<prefix>-<number>[-<reissue>]-<date>.md` is matched exactly to
   the ID, in the folder of its prefix (`lei` → `leis-ordinarias`…); folders starting with `_` are never read. One
   exception: an MP cited without its reissue number (`mpv:2158-2001`) is its last reissue that year
   (`mpv-2158-35`), the one EC 32/2001 kept in force. No other guessing: a wrong ID upstream stays a stub.
4. **Status, conservatively** (`ctresb_leis.estado`):
   - `revogada: true`, or `situacao` "Revogada" → `revogada`.
   - An MP "Reeditada", "Reeditada com alteração" or "Convertida em Lei" → `revogada`, with the reason in
     `estado_motivo`; shown as "FORA DE VIGOR (Reeditada)".
   - `forca_legal_fonte` with `NotInForce` → `revogada`, reason "sem vigência segundo os metadados de normas.leg.br".
   - `revogada: false` → `vigente`.
   - `revogada: null` → a new state, **`sem_informacao`** ("SITUAÇÃO NÃO INFORMADA"): never shown as in force, and
     `vigencia_em` answers `indeterminada`. It is only ever set for federal acts; upstream's `estado.jsonl` still
     accepts only its three values.
5. **Text over time.** The graph has no amendment history for federal acts. `vigencia_em` treats an act's stored
   text as the wording of a date only when it is a compiled text and the date is between its download (`baixado_em`)
   and today; an `original` text is never that date's wording. Every answer shows `versao_texto`
   (CLAUDE.md: never present `original` text as current wording).
6. **Same pipeline otherwise.** Federal acts are split into Dispositivos like the norms (ADR 0001), and their text is
   read for citations (ADR 0004), but a citation there of a norm not in the graph is dropped (no stub, no waiting).
   `acervo` is the ID prefix (`lei`, `dec`…), `orgao` "Congresso Nacional" (laws) or "Presidência da República"
   (decrees, MPs, decree-laws, delegated laws), `fonte_url` the normas.leg.br link, `urn` the LexML URN.

## Measured result (first load, 2026-11-19, ctresb/leis@c9f21b4a)

1,628 federal acts loaded (1,622 exact, 6 MPs by reissue), 317 IDs stay stubs. 40,111 Dispositivos; 28,088
citations from their text. By state: laws 467 in force / 48 revoked; decrees 124 / 195 / 200 with no information;
MPs 177 / 143 / 21; decree-laws 170 / 49; complementary laws 30 / 3; the one delegated law revoked. First load 69 s
including the clone; a run with nothing new lists the trees and returns.

## Known limits

- No amendment history for federal acts, and no federal-to-federal relations other than citations in text.
- An `original` text of an act amended since is shown as published, flagged; the current wording is on
  normas.leg.br.
- A wrong federal ID upstream stays a stub (the stats page lists federal acts upstream couldn't resolve).

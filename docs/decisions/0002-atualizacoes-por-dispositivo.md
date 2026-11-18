# 0002. Reading `atualizacoes` into article-level amendments

Date: 2026-11-18. Status: accepted. Roadmap step 7.

## Context

Upstream lists, in each amended norm's frontmatter, who amended it and how, as free text:

```
Resolução BCB nº 589/2026 - Alteração, a partir de 1º/1/2027 - Nova redação: art. 88, inciso III, alíneas "b",
"c", "d" e "e". Inclusão: arts. 90-A e 90-B.
CIRCULAR BCB 1932/91 DOU 11/04/1991 PAG 6717 - ALTERACAO: ART/7 PARAG/1 ITEM/IV (REGULAMENTO).
```

Upstream's own `grafo.py` turns each entry into a norm-to-norm edge (who, and the relation) and ignores the rest.
The rest is what `vigencia_em` needs. What the corpus looks like (normas-bcb 39a59edc; normas-cvm has no
`atualizacoes`, its history is in `notas`): 18,860 entries in 13,116 norms, in two eras: modern prose ("Nova
redação: art. 88…") and an uppercase code until about 2010 (`ALTERACAO: ART/1 ITEM/IV`, `ANEXO/XV`, `AL/B`).
12,654 are whole-norm revocations.

## Decision

1. **The amending norm is read with upstream's rules**, ported to `parse/citacoes.py` (MIT, credited). The ID we
   name is the one on upstream's edge: 18,827 of 18,833 entries match an upstream edge; the other 6 name the norm
   itself as its amender (an upstream data error, reported as a note).
2. **Targets at article level** (ADR 0001): articles, annexes, top-level items, the preamble. §, inciso, alínea and
   caput are kept as text on the edge (`detalhe`).
3. **Clause grammar**, deterministic: action words open clauses (nova redação / alteração → `nova_redacao`,
   inclusão / acréscimo → `inclusao`, revogação → `revogacao`; prorrogação, citação, renumeração… change no
   wording). "a partir de <date>" applies forward, or to the targets before it when it closes their group
   (`art. 9º (a partir de 6/2/2009)`). An annex followed by a dash, colon or article ("Alteração no Anexo I -
   Nova redação: art. 24") is the scope of the articles after it; otherwise it is itself a target. A clause that
   names another norm is about that norm and is skipped.
4. **Matching to the split** (`ligar`): `Anexo 1` = `anexo-i`; an unnumbered "Regulamento anexo" is the norm's only
   annex; an article missing from the main body is the one in the only annex that has it.
5. **Nothing is dropped.** Every entry becomes an `(:Atualizacao)` node with how it was read; the stats page lists
   every `falha` and every `parcial` with an unreadable clause. Targets that match no Dispositivo are stored on the
   entry (key, type, date), because many are real: Res. BCB 589 includes arts. 90-A and 90-B of Res. BCB 520 from
   1/1/2027, and the portal's consolidated text doesn't have them yet.
6. **Edges are rebuilt with the norm.** Entries live in the amended norm's file, so its entries and the `ALTERA`
   edges into its Dispositivos are replaced whenever that norm is read. The parser is versioned like the splitter
   (`atualizacoes.VERSAO` on `(:Ingestao)`): a new version forces a full reload.

`(:Atualizacao)` is a node label not in CLAUDE.md's v1 model: it holds the report and the unmatched targets, which
an edge can't (an edge needs a Dispositivo at both ends).

## Measured result (first load, 2026-11-18)

| Result | Entries |
|---|---|
| whole norm (total revocation 12,654; no detail 554; consolidated manual 433; ementa 1) | 13,642 |
| every target matched | 3,935 |
| read, no target among the norm's Dispositivos | 819 |
| read in part | 293 |
| note (observation, another norm, self-reference) | 57 |
| not read | 114 |

10,301 article-level `ALTERA` edges: nova_redacao 5,461, revogacao 2,879, inclusao 1,961; 3,625 with a start date,
69 after the load date. Full reload with the parser: about 45 s.

Of the 819 entries with no matching target, most are in norms our splitter keeps whole (old, fixed-width or revoked
texts) or with no text on the portal; the rest are inclusions not yet in the consolidated text. The 114 failures are
mostly entries with no article (`Alteração: § 1º`), prose ("TRATA DE OPERAÇÕES…"), or typos ("Revoção total").

## Known limits

- A date in the middle of a list, or two "produzindo efeitos" dates in one clause, is read positionally.
- Several annexes named together as a heading ("Anexos I e II - Nova redação: art. 3º") scope the articles to the
  last one.
- A hyphenated article number upstream writes inconsistently (`art. 9º-B` vs `9-B`) is fine; a letter-only
  reference ("item a") is not read.

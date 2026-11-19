# 0004. Citations read from article text, and what `nao_resolvidos` is

Date: 2026-11-19. Status: accepted. Roadmap step 8.

## Context

Upstream's edges come from frontmatter fields (`referencias`, `normas_vinculadas`, `atualizacoes`…) and link norms to
norms. The text of the articles names many more norms: "nos termos do art. 9º da Lei nº 4.595, de 31 de dezembro de
1964", "Ficam revogadas as Resoluções nºs 4.855 e 4.858". CLAUDE.md's model has `(:Dispositivo)-[:CITA {fonte:
"texto"}]->(:Norma)` for them, and the roadmap asked to shrink `nao_resolvidos`, upstream's list of 3,509 references
it couldn't resolve.

Measured on the 175,657 Dispositivos with text (2026-11-19): upstream's reference rules, as they are, find 23,749
citations to corpus norms; most article text writes the year in words ("de 25 de novembro de 2021") or as "de 2021",
which those rules don't read.

## Decision

1. **Same IDs as upstream.** The extractor (`parse/citacoes_texto.py`) runs upstream's ported rules
   (`parse/citacoes.py`) over a prepared text, so a cited norm gets the ID upstream's own edges give it.
2. **What the extractor adds for running text:**
   - Dates in words and "de 2021" carry the year, as "4.966/2021" does.
   - The year may be missing for BCB/CVM series (their IDs have none). A reference whose ID needs one (federal law,
     `ext:`) and has none is skipped.
   - **The issuer after the number**, which upstream doesn't read: "Resolução nº 1.289, de 20 de março de 1987, do
     Conselho Monetário Nacional", "Decisão Conjunta nº 10/2002, do Banco Central do Brasil e da Comissão de Valores
     Mobiliários", "Portaria nº 327/1977, do Ministério da Fazenda", "Ofício Circular nº 3/2022-CVM/SRE". This is the
     one place where our IDs differ from what upstream's rules would give: we follow the text.
   - A "Resolução" dated before 2020 is the CMN's, even in a CVM text or "do Banco Central": the Resolução BCB and
     Resolução CVM series start in 2020. Upstream reads an issuer-less "Resolução" in a CVM text as a CVM one.
3. **What is not a citation:**
   - The portal's notes on the consolidated text ("(Redação dada pela Resolução CMN nº 5.100…)", "(Incluído…)",
     "Documento normativo revogado pela…"). They record who amended the norm, which `atualizacoes` and upstream's
     edges already have, in the other direction; read as citations, every amended article would "cite" its amender
     (4,330 such false citations to corpus norms).
   - The norm itself, including the portal's heading "Resolução Nº 589" (no issuer) in Res. BCB 589.
   - Lists of numbers after a singular ("Circular nº 3.978/2020, 5 dias"), numbers separated only by spaces (tables),
     "nº 0", and numbers longer than six digits (CNPJs).
4. **Targets.** A corpus norm or an existing stub gets the edge. A federal law or `ext:` norm gets a stub, as
   upstream's edge endpoints do. A BCB/CVM ID that matches no norm gets **no node** (we don't invent corpus norms):
   it waits in `Dispositivo.cita_sem_alvo` and is linked at the end of any run in which the norm exists (loaded by
   the other upstream, or added upstream later). The stats page lists the most cited ones.
5. **Lifecycle.** Citations are rebuilt with the norm's Dispositivos, and versioned like the splitter and the
   `atualizacoes` parser (`citacoes_texto.VERSAO` on `(:Ingestao)`; a new version forces a full reload).
6. **`nao_resolvidos` is classified, not shrunk.** Upstream's list is mostly not resolvable by anyone:

   | Kind | References | Occurrences |
   |---|---|---|
   | another body's norm (FIRCE, DECAM, Portaria MF…; no corpus has them) | 1,562 | 3,126 |
   | section of a BCB manual (MCR, MNI, CNC, RMCCI, COSIF…) | 1,103 | 2,350 |
   | fragment with no recognizable norm ("SUMULA:", "DOU … PAG 481", "RESOLUÇÃO 5783/6") | 600 | 1,180 |
   | federal law upstream has no file for (step 9) | 116 | 165 |
   | BCB/CVM number that doesn't exist (typo upstream, or a missing norm) | 77 | 113 |
   | Constitution / ADCT | 38 | 67 |
   | board vote ("Voto 11/2023–BCB") | 13 | 106 |

   `query.estatisticas.categoria` does the classification (deterministic rules over the pattern or ID); the stats
   page shows it and lists every BCB/CVM ID by name. Step 9 shrinks the federal-law part for real.

## Measured result (2026-11-19, normas-bcb@808e7ca7, normas-cvm@d3972fbd)

157,786 citation edges from 80,003 Dispositivos: corpus norms 111,961, federal laws 41,809, other bodies 3,967.
137,834 distinct norm pairs, 80,772 of them with no edge upstream. 392 citations wait for a BCB/CVM norm the graph
doesn't have. Extraction adds about 30 s to a full load (bcb 68 s, cvm 13 s).

## Known limits

- A state decree ("Decreto 3271/2000, do Governador do Paraná") reads as a federal one.
- A citation with no year of a norm whose ID needs one (most often "Lei nº 6.404", without "/76") is not read.
- An issuer-less "Resolução nº 1.660" with no year in a CVM text keeps upstream's default (CVM) and waits forever.
- Citations name norms, not articles: "art. 9º da Lei 4.595" links to Lei 4.595.
- `relacoes` and the neighborhood graph still traverse norm-level edges only.

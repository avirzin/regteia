# 0001. Dispositivos at article granularity

Date: 2026-11-12. Status: accepted. Roadmap step 5.

## Context

Step 5 splits each norm's text into `Dispositivo` nodes for full-text search, and step 7 links article-level
amendments (`ALTERA` from upstream's `atualizacoes`) to them. We had to choose how fine to cut: the article, or down
to paragraph (§), inciso and alínea.

What the corpus looks like (normas-bcb 9e353a7b + normas-cvm 4a394582, 63,585 norms, 277 MB of body text):

- Modern series are article-structured: all 604 Resoluções BCB, 785 of 786 Instruções Normativas BCB, 597 of 627
  Instruções CVM. Old CMN resolutions and circulares often use top-level Roman items (`I - Instituir…`) instead.
  Comunicados (43,927) are mostly unstructured auction notices.
- Of 18,860 upstream `atualizacoes` strings, about 3,200 name articles, about 330 name top-level items ("item I"),
  about 575 an annex or "Regulamento". Most (15,800) are whole-norm events ("Revogação total").
- The text is uneven: hard-wrapped PDF conversions (2,937 article headings broken across two lines), fixed-width
  1960s–90s texts, OCR, and consolidated texts that keep superseded wording struck through (`~~…~~`, 391 files).

## Decision

One `Dispositivo` per article. Paragraphs, incisos and alíneas stay inside their article's text. Besides articles:
the preamble, each annex (with its own articles when it has them, `#anexo-i/art-2`), the top-level items of old
norms (`#item-iii`), and a single `#texto` for norms with no recognizable structure, so search still covers them.

The split is deterministic (regex + sequence rules, `ingest/parse/dispositivos.py`), and is versioned: changing the
rules bumps `VERSAO`, and the next ingest notices the mismatch on `(:Ingestao).divisao` and reloads everything.

Struck-through wording is kept, but out of `texto`: `texto` is the latest published wording, `redacoes_anteriores`
the superseded parts. Search then never matches wording that was replaced, and step 7 can use the old wording.
An article that only exists struck through, or reads just "(Revogado…)", is `revogado: true`.

## Why not finer

- Upstream amendments name "art. 88, inciso III, alíneas b e c" often, but splitting incisos and alíneas reliably
  across 60 years of formatting (and OCR) is a much bigger parser, with many more ways to be silently wrong.
  Article-level `ALTERA` edges already answer "was this article changed, and from when"; the inciso can be stored on
  the edge as text (step 7) without being a node.
- 175,576 nodes at article level; incisos and alíneas would multiply that several times, for little search gain
  (an article is a good search hit: short enough to read, long enough to have context).

We can go finer later for articles that need it, without changing article IDs: `#art-88/inc-iii` would be a child.

## Measured result (first load)

175,576 Dispositivos (67,193 articles, 42,647 items, 2,194 annexes, 20,619 preambles, 42,923 whole texts).
Norms: 9,512 split by articles, 11,133 by items, 42,904 whole text, 36 with no text on the portal.
256 revoked articles; 2,278 Dispositivos with earlier wording. Split time: about 20 s for the whole corpus;
full load with Dispositivos: about 65 s.

Known limits: 74 gaps in article numbering remain out of about 100,000 articles. The ones checked are articles
missing from upstream's text or headings in unusual forms (`(*) ART. 3º.`); their text stays inside the previous
article, nothing is lost. Quoted articles of other norms inside amending norms stay inside the amending article,
also when the portal dropped the opening quote.

# Test fixtures

Real upstream files, copied verbatim, never edited by hand:

- `normas-bcb/`, `normas-cvm/`: 20 norm files (incl. Resolução BCB 520 and 589, OCR, PDF-only, cancelled,
  metadata-only, revoked, CVM with `notas`/`revogada_por`/`temas`) laid out exactly as upstream.
- `*/grafo/`: an excerpt of upstream's graph files: `estado.jsonl` rows for those norms, every `arestas.jsonl` edge
  leaving them, the matching `externos.jsonl` rows, and one real `nao_resolvidos.jsonl` row of each shape.
  Plus the `revoga` edges into Circular 1 and Carta Circular 1 (normas-bcb@28124085), for `vigencia_em`.

- `leis/`: five federal acts from ctresb/leis@c9f21b4a (2026-11-02) that the normas fixtures point to (Lei 4.595,
  compiled text; Lei 14.478, original text; Decreto 11.563; Decreto 4.334, `revogada: null`; MP 2.200-2, in force
  by EC 32), plus Decreto 96.673/1988 (`NotInForce`), which nothing points to and so must not be loaded. The
  `README.md` there is ours (a sparse checkout needs one file to start from).

Taken from normas-bcb@39a59edc and normas-cvm@7d8ffce9 (2026-11-11). Official acts: not protected by copyright
(Lei nº 9.610/1998, art. 8º, IV).

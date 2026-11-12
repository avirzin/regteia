# Test fixtures

Real upstream files, copied verbatim, never edited by hand:

- `normas-bcb/`, `normas-cvm/`: 20 norm files (incl. Resolução BCB 520 and 589, OCR, PDF-only, cancelled,
  metadata-only, revoked, CVM with `notas`/`revogada_por`/`temas`) laid out exactly as upstream.
- `*/grafo/`: an excerpt of upstream's graph files: `estado.jsonl` rows for those norms, every `arestas.jsonl` edge
  leaving them, the matching `externos.jsonl` rows, and one real `nao_resolvidos.jsonl` row of each shape.

Taken from normas-bcb@39a59edc and normas-cvm@7d8ffce9 (2026-11-11). Official acts: not protected by copyright
(Lei nº 9.610/1998, art. 8º, IV).

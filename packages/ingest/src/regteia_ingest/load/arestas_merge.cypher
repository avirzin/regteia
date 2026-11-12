// Norm-to-norm relations from grafo/arestas.jsonl. Relationship types cannot be parameters, so each upstream
// `relacao` gets its own MERGE, selected with the FOREACH/CASE idiom. Keyed by (de, para, type, upstream).
UNWIND $rows AS row
MATCH (de:Norma {id: row.de})
MATCH (para:Norma {id: row.para})
FOREACH (_ IN CASE row.relacao WHEN 'revoga' THEN [1] ELSE [] END |
  MERGE (de)-[r:REVOGA {upstream: $upstream}]->(para)
  SET r.desde = row.desde, r.fonte = row.fonte, r.ingestao = $run)
FOREACH (_ IN CASE row.relacao WHEN 'revoga_parcial' THEN [1] ELSE [] END |
  MERGE (de)-[r:REVOGA_PARCIAL {upstream: $upstream}]->(para)
  SET r.desde = row.desde, r.fonte = row.fonte, r.ingestao = $run)
FOREACH (_ IN CASE row.relacao WHEN 'altera' THEN [1] ELSE [] END |
  MERGE (de)-[r:ALTERA {upstream: $upstream}]->(para)
  SET r.desde = row.desde, r.fonte = row.fonte, r.ingestao = $run)
FOREACH (_ IN CASE row.relacao WHEN 'cita' THEN [1] ELSE [] END |
  MERGE (de)-[r:CITA {upstream: $upstream}]->(para)
  SET r.desde = row.desde, r.fonte = row.fonte, r.ingestao = $run)
FOREACH (_ IN CASE row.relacao WHEN 'regulamenta' THEN [1] ELSE [] END |
  MERGE (de)-[r:REGULAMENTA {upstream: $upstream}]->(para)
  SET r.desde = row.desde, r.fonte = row.fonte, r.ingestao = $run)
FOREACH (_ IN CASE row.relacao WHEN 'conjunta' THEN [1] ELSE [] END |
  MERGE (de)-[r:CONJUNTA {upstream: $upstream}]->(para)
  SET r.desde = row.desde, r.fonte = row.fonte, r.ingestao = $run)
RETURN count(*) AS n

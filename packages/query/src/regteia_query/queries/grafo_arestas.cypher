// Overview export: norm-to-norm edges, deduplicated across upstreams.
MATCH (a:Norma)-[r]->(b:Norma)
WHERE $comunicados OR (NOT a.id STARTS WITH 'bcb:comunicado:' AND NOT b.id STARTS WITH 'bcb:comunicado:')
RETURN DISTINCT a.id AS de, b.id AS para, type(r) AS tipo

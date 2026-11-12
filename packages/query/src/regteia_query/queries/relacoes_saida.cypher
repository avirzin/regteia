// One BFS hop outwards from $ids. Comunicados (mostly auction notices) are skipped unless asked for.
UNWIND $ids AS id
MATCH (a:Norma {id: id})-[r]->(b:Norma)
WHERE type(r) IN $tipos AND ($comunicados OR NOT b.id STARTS WITH 'bcb:comunicado:')
RETURN a.id AS de, b.id AS para, b.id AS vizinho, type(r) AS tipo, r.desde AS desde, r.fonte AS fonte
ORDER BY coalesce(b.data, date('0001-01-01')) DESC, b.id, tipo
LIMIT $limite

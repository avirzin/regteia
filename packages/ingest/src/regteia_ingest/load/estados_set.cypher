// Apply grafo/estado.jsonl (the authoritative validity status) to norms already loaded. `estado_por`: the norms
// upstream says revoked or amended this one (empty list removes the property).
UNWIND $rows AS row
MATCH (n:Norma {id: row.id})
SET n.estado = row.estado, n.caminho = row.caminho,
    n.estado_por = CASE WHEN size(row.por) > 0 THEN row.por END
RETURN count(n) AS n

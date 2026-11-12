// Apply grafo/estado.jsonl (the authoritative validity status) to norms already loaded.
UNWIND $rows AS row
MATCH (n:Norma {id: row.id})
SET n.estado = row.estado, n.caminho = row.caminho
RETURN count(n) AS n

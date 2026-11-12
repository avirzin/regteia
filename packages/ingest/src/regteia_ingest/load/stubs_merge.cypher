// Edge endpoints with no upstream file get a stub node. Never overwrites a norm that has a file.
UNWIND $rows AS row
MERGE (n:Norma {id: row.id})
ON CREATE SET n.externo = true, n.acervo = row.acervo
RETURN count(n) AS n

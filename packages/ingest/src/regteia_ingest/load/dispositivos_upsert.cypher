// Upsert the Dispositivos of a batch of norms and record how each norm was split. Rows: {norma, divisao, itens}.
UNWIND $rows AS row
MATCH (n:Norma {id: row.norma})
SET n.divisao = row.divisao
WITH n, row
UNWIND row.itens AS item
MERGE (d:Dispositivo {id: item.id})
SET d += item, d.ingestao = $run
MERGE (n)-[:TEM_DISPOSITIVO]->(d)
RETURN count(d) AS n

// grafo/externos.jsonl: where a referenced norm lives (another repo or ctresb/leis).
UNWIND $rows AS row
MERGE (n:Norma {id: row.id})
ON CREATE SET n.externo = true, n.acervo = row.acervo
SET n.url_externa = row.url
RETURN count(n) AS n

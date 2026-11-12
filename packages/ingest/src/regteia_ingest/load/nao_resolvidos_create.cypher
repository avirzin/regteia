// grafo/nao_resolvidos.jsonl: references upstream could not resolve. Replaced as a whole on every graph reload.
UNWIND $rows AS row
CREATE (x:NaoResolvido)
SET x = row, x.upstream = $upstream
RETURN count(x) AS n

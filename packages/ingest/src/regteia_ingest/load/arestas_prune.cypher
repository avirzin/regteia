// Remove norm-to-norm edges of this upstream that are no longer in its arestas.jsonl.
MATCH (:Norma)-[r:REVOGA|REVOGA_PARCIAL|ALTERA|CITA|REGULAMENTA|CONJUNTA]->(:Norma)
WHERE r.upstream = $upstream AND r.ingestao <> $run
DELETE r
RETURN count(*) AS n

MATCH (n:Norma)
WITH count(CASE WHEN n.externo = false THEN 1 END) AS normas, count(CASE WHEN n.externo THEN 1 END) AS stubs,
     count(CASE WHEN n.ocr THEN 1 END) AS ocr
CALL () { MATCH (:Norma)-[r]->(:Norma) RETURN count(r) AS arestas }
CALL () { MATCH (x:NaoResolvido) RETURN count(x) AS nao_resolvidos }
RETURN normas, stubs, ocr, arestas, nao_resolvidos

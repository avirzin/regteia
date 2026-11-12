MATCH (n:Norma {externo: true})
RETURN n.acervo AS acervo, count(*) AS n
ORDER BY n DESC

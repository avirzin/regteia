// Dispositivo coverage per series and split method.
MATCH (n:Norma {externo: false})
OPTIONAL MATCH (n)-[:TEM_DISPOSITIVO]->(d:Dispositivo)
WITH n, count(d) AS ds, count(CASE WHEN d.tipo = 'artigo' THEN 1 END) AS arts,
     count(CASE WHEN d.revogado THEN 1 END) AS rev, count(CASE WHEN d.redacoes_anteriores IS NOT NULL THEN 1 END) AS ant
RETURN n.acervo AS acervo, split(n.id, ':')[1] AS serie, coalesce(n.divisao, '?') AS divisao, count(n) AS normas,
       sum(ds) AS dispositivos, sum(arts) AS artigos, sum(rev) AS revogados, sum(ant) AS com_redacao_anterior
ORDER BY acervo, serie, divisao

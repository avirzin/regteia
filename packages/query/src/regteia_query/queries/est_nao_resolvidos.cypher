MATCH (x:NaoResolvido)
RETURN x.upstream AS upstream, x.tipo AS tipo, x.campo AS campo, count(*) AS n,
       sum(coalesce(x.arestas, x.trechos, 0)) AS ocorrencias
ORDER BY n DESC

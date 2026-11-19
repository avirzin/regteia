// Every upstream unresolved reference, for classifying (estatisticas.categoria): a few thousand rows.
MATCH (x:NaoResolvido)
OPTIONAL MATCH (em:Norma {id: x.em})
RETURN x.tipo AS tipo, x.id AS id, x.padrao AS padrao, x.exemplo AS exemplo, x.em AS em, em.titulo AS titulo,
       x.campo AS campo, coalesce(x.arestas, x.trechos, 1) AS ocorrencias

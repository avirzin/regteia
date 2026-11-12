MATCH (:Norma)-[r]->(:Norma)
RETURN type(r) AS relacao, r.fonte AS fonte, r.upstream AS upstream, count(*) AS n,
       count(r.desde) AS com_desde
ORDER BY relacao, fonte

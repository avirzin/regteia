// Federal acts the BCB/CVM corpora point to: any edge between them and a BCB/CVM norm (either direction), a citation
// in a BCB/CVM Dispositivo, or an article-level amendment they made to one. Citations in other federal acts' text
// don't count, or every law would pull in the laws it cites.
MATCH (n:Norma)
WHERE split(n.id, ':')[0] IN $prefixos
  AND (EXISTS { MATCH (n)--(o:Norma) WHERE o.acervo IN ['bcb', 'cvm'] }
       OR EXISTS { MATCH (o:Norma)-[:TEM_DISPOSITIVO]->(:Dispositivo)-[:CITA]->(n) WHERE o.acervo IN ['bcb', 'cvm'] }
       OR EXISTS { MATCH (n)-[:ALTERA]->(:Dispositivo) })
RETURN n.id AS id

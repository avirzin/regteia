// The parse-failure report: entries we could not read, or read only in part. Newest norms first.
MATCH (n:Norma)-[:TEM_ATUALIZACAO]->(a:Atualizacao)
WHERE a.resultado = 'falha' OR (a.resultado IN ['parcial', 'ausente'] AND a.motivo IS NOT NULL)
RETURN n.id AS norma, n.titulo AS titulo, a.texto AS texto, a.resultado AS resultado, a.motivo AS motivo
ORDER BY n.data DESC, a.ordem
LIMIT 500

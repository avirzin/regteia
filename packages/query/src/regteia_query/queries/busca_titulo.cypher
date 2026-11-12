// Fallback for resolving a norm by name: full-text over titles only, file-backed norms first.
CALL db.index.fulltext.queryNodes('busca_pt', $q, {limit: 50}) YIELD node, score
WHERE node:Norma AND node.externo = false
RETURN node.id AS id, node.titulo AS titulo, score
ORDER BY score DESC
LIMIT $limite

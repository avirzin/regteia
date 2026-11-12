// Full-text search (brazilian analyzer). Comunicados (mostly auction notices) are multiplied by $peso_comunicado.
CALL db.index.fulltext.queryNodes('busca_pt', $q, {limit: $candidatos}) YIELD node, score
WHERE node:Norma AND ($incluir_revogadas OR node.estado <> 'revogada')
WITH node AS n, score * CASE WHEN node.id STARTS WITH 'bcb:comunicado:' THEN $peso_comunicado ELSE 1.0 END AS score
RETURN n {.id, .titulo, .tipo, .orgao, .data, .estado, .externo, .acervo, .ementa, .fonte_url, .url_arquivo,
          .url_externa, .versao_texto, .ocr, .cancelada} AS n, score
ORDER BY score DESC
LIMIT $limite

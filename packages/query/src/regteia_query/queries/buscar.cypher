// Full-text search (brazilian analyzer) over norm titles/ementas and Dispositivo texts, grouped by norm.
// A norm scores its best hit; comunicados are multiplied by $peso_comunicado. For Dispositivo hits, the best
// $por_norma come back with the start of their text (capped) so the caller can cut an excerpt.
CALL db.index.fulltext.queryNodes('busca_pt', $q, {limit: $candidatos}) YIELD node, score
OPTIONAL MATCH (dono:Norma)-[:TEM_DISPOSITIVO]->(node)
WITH coalesce(dono, node) AS n, CASE WHEN node:Dispositivo THEN node END AS d, score
WHERE n:Norma AND ($incluir_revogadas OR n.estado <> 'revogada')
WITH n, d, score * CASE WHEN n.id STARTS WITH 'bcb:comunicado:' THEN $peso_comunicado ELSE 1.0 END AS score
ORDER BY score DESC
WITH n, max(score) AS score,
     collect(CASE WHEN d IS NOT NULL THEN {id: d.id, tipo: d.tipo, rotulo: d.rotulo, revogado: d.revogado,
             contexto: d.contexto, texto: left(d.texto, $texto_max), score: score} END) AS ds
RETURN n {.id, .titulo, .tipo, .orgao, .data, .estado, .externo, .acervo, .ementa, .fonte_url, .url_arquivo,
          .url_externa, .versao_texto, .ocr, .cancelada,
          estado_por: COLLECT { MATCH (p:Norma) WHERE p.id IN coalesce(n.estado_por, [])
                                RETURN coalesce(p.titulo, p.id) ORDER BY p.data, p.id }} AS n, score, ds[0..$por_norma] AS trechos
ORDER BY score DESC
LIMIT $limite

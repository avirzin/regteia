// One norm's direct relations, grouped by direction and type: the total, plus the most recent `$limite` items.
MATCH (n:Norma {id: $id})
CALL (n) {
  MATCH (n)-[r]->(m:Norma) RETURN 'saida' AS direcao, r, m
  UNION ALL
  MATCH (n)<-[r]-(m:Norma) RETURN 'entrada' AS direcao, r, m
}
WITH direcao, type(r) AS tipo, r, m
ORDER BY coalesce(m.data, date('0001-01-01')) DESC, m.id
WITH direcao, tipo, count(*) AS total,
     collect({
       norma: m {.id, .titulo, .tipo, .orgao, .data, .estado, .externo, .acervo, .ementa, .fonte_url, .url_arquivo,
                 .url_externa, .versao_texto, .ocr, .cancelada},
       desde: r.desde, fonte: r.fonte
     })[..$limite] AS itens
RETURN direcao, tipo, total, itens
ORDER BY direcao, tipo

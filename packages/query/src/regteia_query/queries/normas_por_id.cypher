UNWIND $ids AS id
MATCH (n:Norma {id: id})
RETURN n {.id, .titulo, .tipo, .orgao, .data, .estado, .externo, .acervo, .ementa, .fonte_url, .url_arquivo,
          .url_externa, .versao_texto, .ocr, .cancelada,
          estado_por: COLLECT { MATCH (p:Norma) WHERE p.id IN coalesce(n.estado_por, [])
                                RETURN coalesce(p.titulo, p.id) ORDER BY p.data, p.id }} AS n

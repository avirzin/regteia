UNWIND $ids AS id
MATCH (n:Norma {id: id})
RETURN n {.id, .titulo, .tipo, .orgao, .data, .estado, .externo, .acervo, .ementa, .fonte_url, .url_arquivo,
          .url_externa, .versao_texto, .ocr, .cancelada} AS n

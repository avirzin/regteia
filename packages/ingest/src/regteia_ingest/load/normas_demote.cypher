// Norms of this upstream whose file is gone: keep the node (other norms may point to it) but turn it into a stub.
MATCH (n:Norma {upstream: $upstream})
WHERE n.externo = false AND NOT n.id IN $vivos
SET n.externo = true
REMOVE n.orgao, n.tipo, n.numero, n.data, n.titulo, n.ementa, n.estado, n.revogada, n.cancelada, n.fonte_url,
       n.caminho, n.upstream, n.upstream_sha, n.url_arquivo, n.versao_texto, n.publicacao, n.responsavel, n.baixado_em,
       n.arquivo, n.ocr, n.temas
RETURN count(n) AS n

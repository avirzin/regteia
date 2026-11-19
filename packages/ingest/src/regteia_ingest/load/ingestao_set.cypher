// Only written after a successful load: the next run diffs from this SHA. `divisao` is the splitter version the
// Dispositivos were built with, `atualizacoes` the version of the atualizacoes parser, `citacoes` the version of the
// body-text citation extractor; a different version of any of them forces a full reload.
MERGE (i:Ingestao {fonte: $fonte})
SET i.sha = $sha, i.em = datetime(), i.arquivos = $arquivos, i.modo = $modo, i.divisao = $divisao, i.atualizacoes = $atualizacoes, i.citacoes = $citacoes

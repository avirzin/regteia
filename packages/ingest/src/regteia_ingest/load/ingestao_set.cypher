// Only written after a successful load: the next run diffs from this SHA. `divisao` is the splitter version the
// Dispositivos were built with; a different version forces a full reload.
MERGE (i:Ingestao {fonte: $fonte})
SET i.sha = $sha, i.em = datetime(), i.arquivos = $arquivos, i.modo = $modo, i.divisao = $divisao

// Only written after a successful load: the next run diffs from this SHA.
MERGE (i:Ingestao {fonte: $fonte})
SET i.sha = $sha, i.em = datetime(), i.arquivos = $arquivos, i.modo = $modo

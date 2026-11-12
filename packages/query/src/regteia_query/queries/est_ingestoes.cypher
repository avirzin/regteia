MATCH (i:Ingestao)
RETURN i.fonte AS fonte, i.sha AS sha, i.em AS em, i.arquivos AS arquivos, i.modo AS modo
ORDER BY fonte

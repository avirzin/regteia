MATCH (i:Ingestao {fonte: $fonte})
RETURN i.sha AS sha

// What the data was loaded from: changes whenever any ingest records a new commit. Used as a cache key.
MATCH (i:Ingestao)
RETURN i.fonte AS fonte, i.sha AS sha, toString(i.em) AS em
ORDER BY fonte

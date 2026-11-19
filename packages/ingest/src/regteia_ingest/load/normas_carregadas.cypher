// One upstream's file-backed norms and the commit each was read at.
MATCH (n:Norma {upstream: $upstream})
WHERE n.externo = false
RETURN n.id AS id, n.upstream_sha AS sha

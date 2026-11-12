MATCH (x:NaoResolvido {upstream: $upstream})
DELETE x
RETURN count(*) AS n

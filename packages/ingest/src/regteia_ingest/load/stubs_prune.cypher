// Stubs nothing points to any more.
MATCH (n:Norma {externo: true})
WHERE NOT (n)--()
DELETE n
RETURN count(*) AS n

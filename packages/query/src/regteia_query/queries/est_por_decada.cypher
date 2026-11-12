MATCH (n:Norma {externo: false})
WHERE n.data IS NOT NULL
RETURN n.orgao AS orgao, (n.data.year / 10) * 10 AS decada, count(*) AS n
ORDER BY decada, orgao

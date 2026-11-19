// File-backed norms per series (the middle part of the id) and validity status.
MATCH (n:Norma {externo: false})
WITH n.acervo AS acervo, CASE WHEN n.acervo IN ['lei', 'lcp', 'ldl', 'del', 'dec', 'mpv'] THEN n.acervo ELSE split(n.id, ':')[1] END AS serie, n.orgao AS orgao, n.estado AS estado
RETURN acervo, serie, orgao, estado, count(*) AS n
ORDER BY acervo, serie, orgao, estado

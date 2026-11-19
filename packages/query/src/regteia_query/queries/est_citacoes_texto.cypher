// Citations read from article text: edges by kind of cited norm, citing Dispositivos, and norm pairs (how many have
// no norm-level edge from upstream's frontmatter between them).
CALL () {
  MATCH (:Dispositivo)-[r:CITA {fonte: 'texto'}]->(m:Norma)
  WITH CASE
         WHEN m.externo = false THEN 'acervo'
         WHEN split(m.id, ':')[0] IN ['lei', 'lcp', 'ldl', 'del', 'dec', 'mpv'] THEN 'lei_federal'
         WHEN m.id STARTS WITH 'ext:' THEN 'outro_orgao'
         ELSE 'fora_do_acervo'
       END AS alvo, count(r) AS n
  RETURN collect({alvo: alvo, n: n}) AS por_alvo
}
CALL () {
  MATCH (d:Dispositivo)-[:CITA {fonte: 'texto'}]->()
  RETURN count(DISTINCT d) AS dispositivos
}
CALL () {
  MATCH (n:Norma)-[:TEM_DISPOSITIVO]->(:Dispositivo)-[:CITA {fonte: 'texto'}]->(m:Norma)
  WHERE n <> m
  WITH DISTINCT n, m
  RETURN count(*) AS pares, count(CASE WHEN NOT (n)-->(m) AND NOT (m)-->(n) THEN 1 END) AS pares_novos
}
CALL () {
  MATCH (d:Dispositivo)
  WHERE d.cita_sem_alvo IS NOT NULL
  RETURN sum(size(d.cita_sem_alvo)) AS pendentes
}
RETURN por_alvo, dispositivos, pares, pares_novos, coalesce(pendentes, 0) AS pendentes

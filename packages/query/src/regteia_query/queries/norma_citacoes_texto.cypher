// Citations in article text, by norm: the norms this norm's Dispositivos cite (saida) and the norms whose Dispositivos
// cite this one (entrada). Per direction: the number of norms, plus the `$limite` with most citing Dispositivos, each
// with its first citing Dispositivos in reading order.
MATCH (n:Norma {id: $id})
CALL (n) {
  MATCH (n)-[:TEM_DISPOSITIVO]->(d:Dispositivo)-[:CITA {fonte: 'texto'}]->(m:Norma)
  RETURN 'saida' AS direcao, m, d
  UNION ALL
  MATCH (m:Norma)-[:TEM_DISPOSITIVO]->(d:Dispositivo)-[:CITA {fonte: 'texto'}]->(n)
  RETURN 'entrada' AS direcao, m, d
}
WITH direcao, m, d
ORDER BY d.ordem
WITH direcao, m, count(d) AS total, collect(d {.id, .tipo, .rotulo, .revogado, .contexto})[..5] AS dispositivos
ORDER BY total DESC, coalesce(m.data, date('0001-01-01')) DESC, m.id
WITH direcao, count(m) AS total,
     collect({
       norma: m {.id, .titulo, .tipo, .orgao, .data, .estado, .externo, .acervo, .fonte_url, .cancelada},
       total: total, dispositivos: dispositivos
     })[..$limite] AS itens
RETURN direcao, total, itens
ORDER BY direcao

// A norm's Dispositivos with their text and the norms each one cites, in reading order.
MATCH (n:Norma {id: $id})
OPTIONAL MATCH (n)-[:TEM_DISPOSITIVO]->(d:Dispositivo)
CALL (d) {
  OPTIONAL MATCH (d)-[r:CITA {fonte: 'texto'}]->(c:Norma)
  WITH r, c ORDER BY r.ordem
  RETURN collect(c {.id, .titulo, .estado, .externo, .acervo}) AS cita
}
WITH n, d, cita ORDER BY d.ordem
RETURN n.divisao AS divisao,
       collect(d {.id, .tipo, .rotulo, .revogado, .contexto, .texto, .redacoes_anteriores, cita: cita}) AS dispositivos

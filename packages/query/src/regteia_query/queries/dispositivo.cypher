// One Dispositivo of a norm, with its neighbours in reading order and the norms its text cites.
MATCH (n:Norma {id: $norma})-[:TEM_DISPOSITIVO]->(d:Dispositivo {id: $id})
OPTIONAL MATCH (n)-[:TEM_DISPOSITIVO]->(a:Dispositivo) WHERE a.ordem = d.ordem - 1
OPTIONAL MATCH (n)-[:TEM_DISPOSITIVO]->(p:Dispositivo) WHERE p.ordem = d.ordem + 1
CALL (d) {
  OPTIONAL MATCH (d)-[r:CITA {fonte: 'texto'}]->(c:Norma)
  WITH r, c ORDER BY r.ordem
  RETURN collect(c {.id, .titulo, .tipo, .orgao, .data, .estado, .externo, .acervo, .fonte_url, .cancelada, .estado_motivo}) AS cita
}
RETURN d {.id, .tipo, .rotulo, .revogado, .contexto, .texto, .redacoes_anteriores} AS d, cita,
       a {.id, .tipo, .rotulo, .revogado, .contexto} AS anterior,
       p {.id, .tipo, .rotulo, .revogado, .contexto} AS proximo

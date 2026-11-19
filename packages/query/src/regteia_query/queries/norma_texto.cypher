// A norm's Dispositivos with their text, in reading order.
MATCH (n:Norma {id: $id})
OPTIONAL MATCH (n)-[:TEM_DISPOSITIVO]->(d:Dispositivo)
WITH n, d ORDER BY d.ordem
RETURN n.divisao AS divisao,
       collect(d {.id, .tipo, .rotulo, .revogado, .contexto, .texto, .redacoes_anteriores}) AS dispositivos

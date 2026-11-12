// One Dispositivo of a norm, with its neighbours in reading order.
MATCH (n:Norma {id: $norma})-[:TEM_DISPOSITIVO]->(d:Dispositivo {id: $id})
OPTIONAL MATCH (n)-[:TEM_DISPOSITIVO]->(a:Dispositivo) WHERE a.ordem = d.ordem - 1
OPTIONAL MATCH (n)-[:TEM_DISPOSITIVO]->(p:Dispositivo) WHERE p.ordem = d.ordem + 1
RETURN d {.id, .tipo, .rotulo, .revogado, .contexto, .texto, .redacoes_anteriores} AS d,
       a {.id, .tipo, .rotulo, .revogado, .contexto} AS anterior,
       p {.id, .tipo, .rotulo, .revogado, .contexto} AS proximo

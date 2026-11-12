// A norm's Dispositivos in order (table of contents), and how its text was split.
MATCH (n:Norma {id: $id})
OPTIONAL MATCH (n)-[:TEM_DISPOSITIVO]->(d:Dispositivo)
WITH n, d ORDER BY d.ordem
RETURN n.divisao AS divisao,
       collect(d {.id, .tipo, .rotulo, .revogado, .contexto}) AS sumario

// Article-level amendments (ALTERA from `atualizacoes`) into the Dispositivos of $norma, or only into $dispositivo,
// with the amending norm's date and the upstream entry each came from.
MATCH (n:Norma {id: $norma})-[:TEM_DISPOSITIVO]->(d:Dispositivo)<-[r:ALTERA {fonte: 'atualizacoes'}]-(de:Norma)
WHERE $dispositivo IS NULL OR d.id = $dispositivo
OPTIONAL MATCH (n)-[:TEM_ATUALIZACAO]->(a:Atualizacao {ordem: r.entrada})
RETURN d.id AS dispositivo, d.rotulo AS rotulo, de.id AS de, de.titulo AS titulo, de.data AS de_data,
       r.tipo AS tipo, r.a_partir_de AS a_partir_de, r.detalhe AS detalhe, a.texto AS entrada
ORDER BY d.ordem, r.entrada

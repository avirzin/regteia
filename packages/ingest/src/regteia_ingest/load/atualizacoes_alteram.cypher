// Article-level amendments: the amending norm -> the Dispositivo, from one `atualizacoes` entry. The amending norm
// may be outside the corpora: it gets a stub, as upstream's edge endpoints do. Rows: {de, acervo, dispositivo, tipo,
// a_partir_de, detalhe, entrada}.
UNWIND $rows AS row
MATCH (d:Dispositivo {id: row.dispositivo})
MERGE (de:Norma {id: row.de})
ON CREATE SET de.externo = true, de.acervo = row.acervo
CREATE (de)-[r:ALTERA {fonte: 'atualizacoes', tipo: row.tipo, entrada: row.entrada}]->(d)
SET r.a_partir_de = CASE WHEN row.a_partir_de IS NULL THEN null ELSE date(row.a_partir_de) END,
    r.detalhe = row.detalhe
RETURN count(r) AS n

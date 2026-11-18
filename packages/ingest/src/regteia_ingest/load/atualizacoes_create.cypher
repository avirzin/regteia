// One node per `atualizacoes` entry of a norm, in upstream's order: the raw text, the amending norm, how it was read,
// and the targets that matched no Dispositivo. Rows: {norma, ordem, texto, de, resultado, motivo, ausentes,
// ausentes_tipo, ausentes_desde}.
UNWIND $rows AS row
MATCH (n:Norma {id: row.norma})
CREATE (a:Atualizacao {id: row.norma + '#atualizacao-' + toString(row.ordem)})
SET a += row, a.ingestao = $run
CREATE (n)-[:TEM_ATUALIZACAO]->(a)
RETURN count(a) AS n

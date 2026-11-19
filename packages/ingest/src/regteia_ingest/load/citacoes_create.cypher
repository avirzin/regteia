// Norms cited in a Dispositivo's text (ADR 0004). A cited norm outside the corpora (a federal law, `ext:`) gets a stub,
// as upstream's edge endpoints do. A BCB or CVM ID that matches no norm gets no node: it waits on the Dispositivo
// (`cita_sem_alvo`) until citacoes_pendentes finds the norm. `ordem` is the order of first mention in the text.
// Rows: {dispositivo, alvo, ordem, acervo, externo}.
UNWIND $rows AS row
MATCH (d:Dispositivo {id: row.dispositivo})
OPTIONAL MATCH (n:Norma {id: row.alvo})
WITH d, row, n IS NOT NULL OR row.externo AS liga
FOREACH (_ IN CASE WHEN liga THEN [1] ELSE [] END |
  MERGE (m:Norma {id: row.alvo})
  ON CREATE SET m.externo = true, m.acervo = row.acervo
  MERGE (d)-[r:CITA {fonte: 'texto'}]->(m)
  SET r.ordem = row.ordem
)
FOREACH (_ IN CASE WHEN liga THEN [] ELSE [1] END |
  SET d.cita_sem_alvo = coalesce(d.cita_sem_alvo, []) + row.alvo
)
RETURN count(*) AS n

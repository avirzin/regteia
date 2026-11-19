// Citations waiting for their norm: link the ones whose norm now exists (loaded later in this run, by the other
// upstream, or in a later run) and keep the rest waiting.
MATCH (d:Dispositivo)
WHERE d.cita_sem_alvo IS NOT NULL
UNWIND d.cita_sem_alvo AS alvo
MATCH (n:Norma {id: alvo})
MERGE (d)-[r:CITA {fonte: 'texto'}]->(n)
SET r.ordem = 1000  // listed after the ones linked when the text was read
WITH d, collect(alvo) AS ligados
WITH d, [x IN d.cita_sem_alvo WHERE NOT x IN ligados] AS resto
SET d.cita_sem_alvo = CASE WHEN resto = [] THEN null ELSE resto END
RETURN count(d) AS n

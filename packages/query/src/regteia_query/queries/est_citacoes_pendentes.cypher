// BCB/CVM norms cited in article text that the graph doesn't have, most cited first.
MATCH (d:Dispositivo)
WHERE d.cita_sem_alvo IS NOT NULL
UNWIND d.cita_sem_alvo AS id
WITH id, count(*) AS dispositivos, min(d.id) AS exemplo
RETURN id, dispositivos, exemplo
ORDER BY dispositivos DESC, id
LIMIT $limite

// Before writing the citations of these norms' Dispositivos again: drop the CITA edges their text made and the
// citations still waiting for their norm (CITA edges from upstream's arestas.jsonl go between norms and are not
// touched).
UNWIND $normas AS id
MATCH (:Norma {id: id})-[:TEM_DISPOSITIVO]->(d:Dispositivo)
CALL (d) {
  MATCH (d)-[r:CITA {fonte: 'texto'}]->(:Norma)
  DELETE r
}
REMOVE d.cita_sem_alvo
RETURN count(d) AS n

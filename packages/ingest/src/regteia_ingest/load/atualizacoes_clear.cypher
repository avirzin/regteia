// Before re-reading the `atualizacoes` of these norms: drop their entries and the article-level ALTERA edges the
// entries made (ALTERA edges from upstream's arestas.jsonl go between norms and are not touched).
UNWIND $normas AS id
MATCH (n:Norma {id: id})
CALL (n) {
  MATCH (n)-[:TEM_ATUALIZACAO]->(a:Atualizacao)
  DETACH DELETE a
}
CALL (n) {
  MATCH (:Norma)-[r:ALTERA {fonte: 'atualizacoes'}]->(:Dispositivo)<-[:TEM_DISPOSITIVO]-(n)
  DELETE r
}
RETURN count(n) AS n

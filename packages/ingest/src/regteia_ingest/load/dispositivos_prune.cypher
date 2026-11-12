// Dispositivos of the norms just re-split that this run did not write (articles that disappeared from the text).
UNWIND $normas AS id
MATCH (:Norma {id: id})-[:TEM_DISPOSITIVO]->(d:Dispositivo)
WHERE d.ingestao <> $run
DETACH DELETE d
RETURN count(*) AS n

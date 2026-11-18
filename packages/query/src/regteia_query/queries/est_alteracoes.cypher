// Article-level amendments read from `atualizacoes`, by type; how many carry a start date, and how many start later.
MATCH (:Norma)-[r:ALTERA {fonte: 'atualizacoes'}]->(:Dispositivo)
RETURN r.tipo AS tipo, count(*) AS n, count(r.a_partir_de) AS com_data,
       sum(CASE WHEN r.a_partir_de > date() THEN 1 ELSE 0 END) AS futuras
ORDER BY n DESC

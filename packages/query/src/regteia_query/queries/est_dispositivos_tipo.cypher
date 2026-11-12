MATCH (d:Dispositivo)
RETURN d.tipo AS tipo, count(*) AS n
ORDER BY n DESC

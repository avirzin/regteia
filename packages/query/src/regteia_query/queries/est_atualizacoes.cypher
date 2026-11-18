// How the `atualizacoes` entries were read (roadmap step 7): dispositivos, parcial, ausente, norma, nota, falha.
MATCH (a:Atualizacao)
RETURN a.resultado AS resultado, count(*) AS n
ORDER BY n DESC

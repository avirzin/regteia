// Overview export: every norm, with just what the overview colors and filters by.
// Comunicados (mostly auction notices) stay out unless asked for.
MATCH (n:Norma)
WHERE $comunicados OR NOT n.id STARTS WITH 'bcb:comunicado:'
RETURN n.id AS id, n.acervo AS acervo, n.orgao AS orgao, n.externo AS externo, n.estado AS estado,
       n.data.year AS ano, n.titulo AS titulo
ORDER BY id

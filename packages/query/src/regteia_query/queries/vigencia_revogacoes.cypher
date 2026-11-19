// Norms that revoke $id, with the edge's date and the revoking norm's own date (the fallback when the edge has none).
MATCH (de:Norma)-[r:REVOGA]->(:Norma {id: $id})
RETURN de.id AS de, de.titulo AS titulo, de.data AS de_data, r.desde AS desde, r.fonte AS fonte
ORDER BY coalesce(desde, de_data), de

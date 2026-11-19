// The `atualizacoes` entries of $norma that edges don't fully cover: targets missing from the text (ausentes) and
// entries read in part, not read, or about the whole norm without detail. With the amending norm's date.
MATCH (:Norma {id: $norma})-[:TEM_ATUALIZACAO]->(a:Atualizacao)
WHERE a.resultado IN ['parcial', 'ausente', 'falha'] OR (a.resultado = 'norma' AND coalesce(a.motivo, '') <> 'revogação total')
OPTIONAL MATCH (de:Norma {id: a.de})
RETURN a.ordem AS ordem, a.texto AS texto, a.resultado AS resultado, a.motivo AS motivo, a.de AS de,
       de.titulo AS titulo, de.data AS de_data, a.ausentes AS ausentes, a.ausentes_tipo AS ausentes_tipo,
       a.ausentes_desde AS ausentes_desde, a.ausentes_detalhe AS ausentes_detalhe
ORDER BY a.ordem

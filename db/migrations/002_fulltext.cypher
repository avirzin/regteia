// Portuguese full-text search over norm titles/summaries and (from roadmap step 5) article text.
CREATE FULLTEXT INDEX busca_pt IF NOT EXISTS
FOR (n:Norma|Dispositivo) ON EACH [n.titulo, n.ementa, n.texto]
OPTIONS {indexConfig: {`fulltext.analyzer`: 'brazilian'}};

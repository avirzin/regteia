// Roadmap step 7: one node per upstream `atualizacoes` entry, and lookups for the stats report and vigencia_em.
CREATE CONSTRAINT atualizacao_id IF NOT EXISTS FOR (a:Atualizacao) REQUIRE a.id IS UNIQUE;
CREATE INDEX atualizacao_resultado IF NOT EXISTS FOR (a:Atualizacao) ON (a.resultado);
CREATE INDEX atualizacao_de IF NOT EXISTS FOR (a:Atualizacao) ON (a.de);

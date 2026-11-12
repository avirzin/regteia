// Unique keys. Upstream IDs are the primary keys.
CREATE CONSTRAINT norma_id IF NOT EXISTS FOR (n:Norma) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT dispositivo_id IF NOT EXISTS FOR (d:Dispositivo) REQUIRE d.id IS UNIQUE;
CREATE CONSTRAINT ingestao_fonte IF NOT EXISTS FOR (i:Ingestao) REQUIRE i.fonte IS UNIQUE;
CREATE CONSTRAINT migracao_nome IF NOT EXISTS FOR (m:Migracao) REQUIRE m.nome IS UNIQUE;

// Lookup indexes used by ingest and statistics.
CREATE INDEX norma_upstream IF NOT EXISTS FOR (n:Norma) ON (n.upstream);
CREATE INDEX norma_externo IF NOT EXISTS FOR (n:Norma) ON (n.externo);
CREATE INDEX norma_estado IF NOT EXISTS FOR (n:Norma) ON (n.estado);
CREATE INDEX norma_tipo IF NOT EXISTS FOR (n:Norma) ON (n.tipo);
CREATE INDEX nao_resolvido_upstream IF NOT EXISTS FOR (x:NaoResolvido) ON (x.upstream);

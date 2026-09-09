-- Additive migration: no existing table or record is replaced.
-- Administración de documentos RAG: enlace directo al id del manifiesto
-- (antes solo inferible por originalFilename), nombre físico real en disco,
-- y estado real de indexación en Qdrant. `indexStatus` por defecto
-- 'INDEXED' preserva el comportamiento de las filas legadas (ya sincronizadas
-- e indexadas por el flujo de arranque existente); se backfillean
-- manifestSourceId/storedFilename la próxima vez que corre
-- sync_knowledge_sources, sin necesidad de un script de migración de datos.
BEGIN TRANSACTION;
ALTER TABLE "KnowledgeSource" ADD COLUMN "manifestSourceId" TEXT;
ALTER TABLE "KnowledgeSource" ADD COLUMN "storedFilename" TEXT;
ALTER TABLE "KnowledgeSource" ADD COLUMN "indexStatus" TEXT NOT NULL DEFAULT 'INDEXED';
ALTER TABLE "KnowledgeSource" ADD COLUMN "indexError" TEXT;
COMMIT;

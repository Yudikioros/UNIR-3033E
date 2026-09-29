-- Additive migration: no existing table or record is replaced.
-- Fase 6: trazabilidad exacta de si una generación usó BAM/RAG. Nula para
-- generaciones históricas (no se infiere retroactivamente lo que no se
-- registró en su momento).
BEGIN TRANSACTION;
ALTER TABLE "AIGeneration" ADD COLUMN "foodDatabaseUsed" BOOLEAN;
ALTER TABLE "AIGeneration" ADD COLUMN "knowledgeBaseUsed" BOOLEAN;
COMMIT;

-- Additive migration: no existing table or record is replaced.
-- Progreso por etapas real durante la generación de borradores: `stage`
-- registra en qué paso del pipeline está una generación (ver GenerationStage
-- en diet_plan_generation.py); `completedAt` marca cuándo terminó (éxito o
-- fallo). Nulos para generaciones históricas previas a esta columna. La fila
-- de AIGeneration ahora se crea al INICIO de la generación (createdAt ya
-- sirve como startedAt real) en vez de al final.
BEGIN TRANSACTION;
ALTER TABLE "AIGeneration" ADD COLUMN "stage" TEXT;
ALTER TABLE "AIGeneration" ADD COLUMN "completedAt" DATETIME;
COMMIT;

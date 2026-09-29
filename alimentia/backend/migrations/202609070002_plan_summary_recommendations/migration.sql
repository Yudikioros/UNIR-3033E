-- Additive migration: no existing table or record is replaced.
-- Fase 6: el LLM ya generaba "summary"/"recommendations" (Fase 4) pero se
-- descartaban antes de persistir. Nulos en planes históricos.
BEGIN TRANSACTION;
ALTER TABLE "DietPlan" ADD COLUMN "summary" TEXT;
ALTER TABLE "DietPlan" ADD COLUMN "recommendations" TEXT;
COMMIT;

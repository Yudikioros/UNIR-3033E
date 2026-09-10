-- Additive migration: no existing table or record is replaced.
-- Trazabilidad del asistente conversacional. Nunca persiste la respuesta
-- completa del LLM ni PII más allá de los IDs de navegación.
BEGIN TRANSACTION;
CREATE TABLE "AssistantInteraction" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "promptVersion" TEXT NOT NULL,
    "model" TEXT NOT NULL,
    "userQuestion" TEXT NOT NULL,
    "navigationContext" TEXT,
    "toolsUsed" TEXT,
    "sourceIds" TEXT,
    "executionTimeMs" INTEGER,
    "status" TEXT NOT NULL,
    "errorMessage" TEXT
);
CREATE INDEX "AssistantInteraction_createdAt_idx" ON "AssistantInteraction"("createdAt");
COMMIT;

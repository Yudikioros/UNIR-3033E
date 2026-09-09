-- Controlled SQLite table rebuild. No legacy row or original JSON is discarded.
PRAGMA foreign_keys=OFF;
BEGIN TRANSACTION;
-- CreateTable
CREATE TABLE "NutritionConsultation" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "patientId" TEXT NOT NULL,
    "consultationDate" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "ageAtConsultation" INTEGER,
    "sex" TEXT,
    "weightKg" REAL,
    "heightM" REAL,
    "activityLevel" TEXT,
    "goal" TEXT,
    "mealsPerDay" INTEGER,
    "dailyBudget" REAL,
    "budgetMin" REAL,
    "budgetMax" REAL,
    "foodPreferences" TEXT,
    "foodsToAvoid" TEXT,
    "allergiesOrIntolerances" TEXT,
    "notes" TEXT,
    "calculationMethod" TEXT,
    "bmi" REAL,
    "basalMetabolicRate" REAL,
    "totalEnergyExpenditure" REAL,
    "targetCalories" REAL,
    "proteinGrams" REAL,
    "carbohydrateGrams" REAL,
    "fatGrams" REAL,
    "fiberGrams" REAL,
    "waterLiters" REAL,
    "calculationRuleVersion" TEXT,
    "calculationDetails" TEXT,
    "legacyPlanId" TEXT,
    "demoKey" TEXT,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "NutritionConsultation_patientId_fkey" FOREIGN KEY ("patientId") REFERENCES "Patient" ("id") ON DELETE RESTRICT ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "DietPlanMeal" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "dietPlanId" TEXT NOT NULL,
    "mealType" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "sortOrder" INTEGER NOT NULL,
    CONSTRAINT "DietPlanMeal_dietPlanId_fkey" FOREIGN KEY ("dietPlanId") REFERENCES "DietPlan" ("id") ON DELETE RESTRICT ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "DietPlanFood" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "dietPlanMealId" TEXT NOT NULL,
    "foodName" TEXT NOT NULL,
    "quantity" REAL CHECK ("quantity" IS NULL OR "quantity" > 0),
    "unit" TEXT,
    "smaeEquivalent" TEXT,
    "calories" REAL,
    "protein" REAL,
    "carbohydrates" REAL,
    "fat" REAL,
    "notes" TEXT,
    "legacyQuantity" TEXT,
    CONSTRAINT "DietPlanFood_dietPlanMealId_fkey" FOREIGN KEY ("dietPlanMealId") REFERENCES "DietPlanMeal" ("id") ON DELETE RESTRICT ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "AIGeneration" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "consultationId" TEXT NOT NULL,
    "dietPlanId" TEXT,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "modelProvider" TEXT NOT NULL,
    "modelName" TEXT NOT NULL,
    "modelVersion" TEXT,
    "promptVersion" TEXT,
    "knowledgeBaseVersion" TEXT,
    "executionTimeMs" INTEGER CHECK ("executionTimeMs" IS NULL OR "executionTimeMs" >= 0),
    "status" TEXT NOT NULL,
    "errorMessage" TEXT,
    "retainPayloads" BOOLEAN NOT NULL DEFAULT false,
    "requestPayload" TEXT,
    "responsePayload" TEXT,
    CHECK ("retainPayloads" OR ("requestPayload" IS NULL AND "responsePayload" IS NULL)),
    CONSTRAINT "AIGeneration_consultationId_fkey" FOREIGN KEY ("consultationId") REFERENCES "NutritionConsultation" ("id") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "AIGeneration_dietPlanId_fkey" FOREIGN KEY ("dietPlanId") REFERENCES "DietPlan" ("id") ON DELETE RESTRICT ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "KnowledgeSource" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "documentName" TEXT NOT NULL,
    "institution" TEXT,
    "version" TEXT,
    "publicationDate" DATETIME,
    "sourceType" TEXT,
    "isActive" BOOLEAN NOT NULL DEFAULT true,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- CreateTable
CREATE TABLE "RetrievedSource" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "generationId" TEXT NOT NULL,
    "knowledgeSourceId" TEXT NOT NULL,
    "section" TEXT,
    "content" TEXT NOT NULL,
    "retrievalScore" REAL,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "RetrievedSource_generationId_fkey" FOREIGN KEY ("generationId") REFERENCES "AIGeneration" ("id") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "RetrievedSource_knowledgeSourceId_fkey" FOREIGN KEY ("knowledgeSourceId") REFERENCES "KnowledgeSource" ("id") ON DELETE RESTRICT ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "PlanValidation" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "dietPlanId" TEXT NOT NULL,
    "severity" TEXT NOT NULL CHECK ("severity" IN ('INFO', 'WARNING', 'ERROR')),
    "code" TEXT NOT NULL,
    "message" TEXT NOT NULL,
    "source" TEXT NOT NULL,
    "isBlocking" BOOLEAN NOT NULL DEFAULT false,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "PlanValidation_dietPlanId_fkey" FOREIGN KEY ("dietPlanId") REFERENCES "DietPlan" ("id") ON DELETE RESTRICT ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "DietPlanChangeLog" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "dietPlanId" TEXT NOT NULL,
    "changedAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "changedBy" TEXT NOT NULL,
    "changeType" TEXT NOT NULL,
    "field" TEXT,
    "previousValue" TEXT,
    "newValue" TEXT,
    "notes" TEXT,
    CONSTRAINT "DietPlanChangeLog_dietPlanId_fkey" FOREIGN KEY ("dietPlanId") REFERENCES "DietPlan" ("id") ON DELETE RESTRICT ON UPDATE CASCADE
);

-- One historical consultation per legacy plan. Unknown measurements stay NULL.
INSERT INTO "NutritionConsultation" ("id", "patientId", "consultationDate", "sex", "goal", "totalEnergyExpenditure", "legacyPlanId", "notes", "createdAt")
SELECT 'legacy-consultation-' || d.id, d.patientId, d.createdAt, p.gender,
       p.goal, d.tdee_calculated, d.id,
       'Imported legacy plan; measurements and calculation rule were not recorded.', d.createdAt
FROM "DietPlan" d JOIN "Patient" p ON p.id = d.patientId;

-- RedefineTables
CREATE TABLE "new_Patient" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "name" TEXT NOT NULL DEFAULT 'Paciente Nuevo',
    "birthDate" DATETIME,
    "age" INTEGER,
    "gender" TEXT NOT NULL,
    "email" TEXT,
    "phone" TEXT,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "defaultActivityLevel" TEXT,
    "defaultGoal" TEXT,
    "defaultMealsPerDay" INTEGER,
    "defaultDailyBudget" REAL,
    "foodPreferences" TEXT,
    "foodsToAvoid" TEXT,
    "allergiesOrIntolerances" TEXT,
    "notes" TEXT,
    "goal" TEXT NOT NULL DEFAULT '',
    "pathologies" TEXT NOT NULL DEFAULT '',
    "demoKey" TEXT
);
INSERT INTO "new_Patient" ("age", "createdAt", "gender", "goal", "id", "name", "pathologies") SELECT "age", "createdAt", "gender", "goal", "id", "name", "pathologies" FROM "Patient";
DROP TABLE "Patient";
ALTER TABLE "new_Patient" RENAME TO "Patient";
CREATE UNIQUE INDEX "Patient_demoKey_key" ON "Patient"("demoKey");
CREATE TABLE "new_DietPlan" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "patientId" TEXT NOT NULL,
    "consultationId" TEXT NOT NULL,
    "version" INTEGER NOT NULL DEFAULT 1 CHECK ("version" > 0),
    "status" TEXT NOT NULL DEFAULT 'DRAFT' CHECK ("status" IN ('DRAFT', 'UNDER_REVIEW', 'MODIFIED', 'REGENERATED', 'REJECTED', 'APPROVED')),
    "totalCalories" REAL,
    "proteinGrams" REAL,
    "carbohydrateGrams" REAL,
    "fatGrams" REAL,
    "fiberGrams" REAL,
    "waterLiters" REAL,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "approvedAt" DATETIME,
    "approvedBy" TEXT,
    "rejectedAt" DATETIME,
    "rejectedBy" TEXT,
    "rejectionReason" TEXT,
    "generationId" TEXT,
    "tdee_calculated" REAL,
    "plan_json" TEXT,
    "legacyStatus" TEXT,
    CONSTRAINT "DietPlan_patientId_fkey" FOREIGN KEY ("patientId") REFERENCES "Patient" ("id") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "DietPlan_consultationId_fkey" FOREIGN KEY ("consultationId") REFERENCES "NutritionConsultation" ("id") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "DietPlan_generationId_fkey" FOREIGN KEY ("generationId") REFERENCES "AIGeneration" ("id") ON DELETE RESTRICT ON UPDATE CASCADE
);
INSERT INTO "new_DietPlan" ("createdAt", "id", "patientId", "consultationId", "plan_json", "status", "legacyStatus", "tdee_calculated")
SELECT "createdAt", "id", "patientId", 'legacy-consultation-' || id, "plan_json",
 CASE status WHEN 'BORRADOR' THEN 'DRAFT' WHEN 'EN REVISIÓN' THEN 'UNDER_REVIEW'
 WHEN 'MODIFICADO' THEN 'MODIFIED' WHEN 'REGENERADO' THEN 'REGENERATED'
 WHEN 'RECHAZADO' THEN 'REJECTED' WHEN 'PLAN APROBADO' THEN 'APPROVED'
 ELSE status END, status, tdee_calculated FROM "DietPlan";
DROP TABLE "DietPlan";
ALTER TABLE "new_DietPlan" RENAME TO "DietPlan";
CREATE UNIQUE INDEX "DietPlan_generationId_key" ON "DietPlan"("generationId");
CREATE INDEX "DietPlan_consultationId_idx" ON "DietPlan"("consultationId");
CREATE INDEX "DietPlan_patientId_idx" ON "DietPlan"("patientId");
CREATE INDEX "DietPlan_status_idx" ON "DietPlan"("status");
CREATE UNIQUE INDEX "DietPlan_consultationId_version_key" ON "DietPlan"("consultationId", "version");

-- CreateIndex
CREATE UNIQUE INDEX "NutritionConsultation_legacyPlanId_key" ON "NutritionConsultation"("legacyPlanId");

-- CreateIndex
CREATE UNIQUE INDEX "NutritionConsultation_demoKey_key" ON "NutritionConsultation"("demoKey");

-- CreateIndex
CREATE INDEX "NutritionConsultation_patientId_idx" ON "NutritionConsultation"("patientId");

-- CreateIndex
CREATE INDEX "NutritionConsultation_consultationDate_idx" ON "NutritionConsultation"("consultationDate");

-- CreateIndex
CREATE UNIQUE INDEX "DietPlanMeal_dietPlanId_sortOrder_key" ON "DietPlanMeal"("dietPlanId", "sortOrder");

-- CreateIndex
CREATE INDEX "DietPlanFood_dietPlanMealId_idx" ON "DietPlanFood"("dietPlanMealId");

-- CreateIndex
CREATE INDEX "AIGeneration_consultationId_idx" ON "AIGeneration"("consultationId");

-- CreateIndex
CREATE INDEX "AIGeneration_dietPlanId_idx" ON "AIGeneration"("dietPlanId");

-- CreateIndex
CREATE INDEX "AIGeneration_createdAt_idx" ON "AIGeneration"("createdAt");

-- CreateIndex
CREATE INDEX "RetrievedSource_generationId_idx" ON "RetrievedSource"("generationId");

-- CreateIndex
CREATE INDEX "RetrievedSource_knowledgeSourceId_idx" ON "RetrievedSource"("knowledgeSourceId");

-- CreateIndex
CREATE INDEX "PlanValidation_dietPlanId_idx" ON "PlanValidation"("dietPlanId");

-- CreateIndex
CREATE INDEX "DietPlanChangeLog_dietPlanId_idx" ON "DietPlanChangeLog"("dietPlanId");

-- CreateIndex
CREATE INDEX "DietPlanChangeLog_changedAt_idx" ON "DietPlanChangeLog"("changedAt");

-- Recover only fields that actually exist in the original JSON.
INSERT INTO "DietPlanMeal" (id, dietPlanId, mealType, name, sortOrder)
SELECT d.id || '-meal-' || m.key, d.id,
 COALESCE(json_extract(m.value, '$.time'), 'LEGACY'),
 COALESCE(json_extract(m.value, '$.time'), 'Comida importada'), CAST(m.key AS INTEGER)
FROM DietPlan d, json_each(CASE WHEN json_valid(d.plan_json) THEN d.plan_json ELSE '{}' END, '$.meals') m
WHERE m.type = 'object';

INSERT INTO "DietPlanFood" (id, dietPlanMealId, foodName, quantity, unit, calories, protein, carbohydrates, fat, notes, legacyQuantity)
SELECT d.id || '-meal-' || m.key || '-food-' || f.key, d.id || '-meal-' || m.key,
 json_extract(f.value, '$.food'),
 CASE WHEN json_type(f.value, '$.quantity') IN ('integer','real') AND json_extract(f.value, '$.quantity') > 0 THEN json_extract(f.value, '$.quantity')
 WHEN json_type(f.value, '$.quantity') = 'text'
 AND instr(json_extract(f.value, '$.quantity'), ' ') > 1
 AND substr(json_extract(f.value, '$.quantity'), 1, instr(json_extract(f.value, '$.quantity'), ' ')-1) = printf('%g', CAST(json_extract(f.value, '$.quantity') AS REAL))
 AND CAST(json_extract(f.value, '$.quantity') AS REAL) > 0
 THEN CAST(json_extract(f.value, '$.quantity') AS REAL) END,
 CASE WHEN json_type(f.value, '$.quantity') = 'text'
 AND instr(json_extract(f.value, '$.quantity'), ' ') > 1
 AND substr(json_extract(f.value, '$.quantity'), 1, instr(json_extract(f.value, '$.quantity'), ' ')-1) = printf('%g', CAST(json_extract(f.value, '$.quantity') AS REAL))
 AND CAST(json_extract(f.value, '$.quantity') AS REAL) > 0
 THEN trim(substr(json_extract(f.value, '$.quantity'), instr(json_extract(f.value, '$.quantity'), ' ')+1))
 ELSE json_extract(f.value, '$.unit') END,
 CASE WHEN json_type(f.value, '$.calories') IN ('integer','real') THEN json_extract(f.value, '$.calories') END,
 CASE WHEN json_type(f.value, '$.protein') IN ('integer','real') THEN json_extract(f.value, '$.protein') END,
 CASE WHEN json_type(f.value, '$.carbs') IN ('integer','real') THEN json_extract(f.value, '$.carbs') END,
 CASE WHEN json_type(f.value, '$.fat') IN ('integer','real') THEN json_extract(f.value, '$.fat') END,
 'Imported from legacy JSON; unstructured values remain in plan_json and legacyQuantity.',
 CAST(json_extract(f.value, '$.quantity') AS TEXT)
FROM DietPlan d,
 json_each(CASE WHEN json_valid(d.plan_json) THEN d.plan_json ELSE '{}' END, '$.meals') m,
 json_each(m.value, '$.items') f
WHERE m.type = 'object' AND f.type = 'object' AND json_type(f.value, '$.food') = 'text';

-- Keep redundant compatibility references consistent at the database boundary.
CREATE TRIGGER DietPlan_consistent_patient_insert BEFORE INSERT ON DietPlan
WHEN NOT EXISTS (SELECT 1 FROM NutritionConsultation c WHERE c.id=NEW.consultationId AND c.patientId=NEW.patientId)
BEGIN SELECT RAISE(ABORT, 'Plan patient must match consultation patient'); END;
CREATE TRIGGER DietPlan_consistent_patient_update BEFORE UPDATE OF patientId, consultationId ON DietPlan
WHEN NOT EXISTS (SELECT 1 FROM NutritionConsultation c WHERE c.id=NEW.consultationId AND c.patientId=NEW.patientId)
BEGIN SELECT RAISE(ABORT, 'Plan patient must match consultation patient'); END;
CREATE TRIGGER Consultation_consistent_patient_update BEFORE UPDATE OF patientId ON NutritionConsultation
WHEN EXISTS (SELECT 1 FROM DietPlan d WHERE d.consultationId=OLD.id AND d.patientId<>NEW.patientId)
BEGIN SELECT RAISE(ABORT, 'Consultation patient conflicts with existing plans'); END;
CREATE TRIGGER Generation_consistent_plan_insert BEFORE INSERT ON AIGeneration
WHEN NEW.dietPlanId IS NOT NULL AND NOT EXISTS (SELECT 1 FROM DietPlan d WHERE d.id=NEW.dietPlanId AND d.consultationId=NEW.consultationId)
BEGIN SELECT RAISE(ABORT, 'Generation must belong to the plan consultation'); END;
CREATE TRIGGER Generation_consistent_plan_update BEFORE UPDATE OF dietPlanId, consultationId ON AIGeneration
WHEN (NEW.dietPlanId IS NOT NULL AND NOT EXISTS (SELECT 1 FROM DietPlan d WHERE d.id=NEW.dietPlanId AND d.consultationId=NEW.consultationId))
 OR EXISTS (SELECT 1 FROM DietPlan d WHERE d.generationId=OLD.id AND (d.consultationId<>NEW.consultationId OR (NEW.dietPlanId IS NOT NULL AND d.id<>NEW.dietPlanId)))
BEGIN SELECT RAISE(ABORT, 'Generation references must remain consistent'); END;
CREATE TRIGGER DietPlan_consistent_generation_insert BEFORE INSERT ON DietPlan
WHEN NEW.generationId IS NOT NULL AND NOT EXISTS (SELECT 1 FROM AIGeneration g WHERE g.id=NEW.generationId AND g.consultationId=NEW.consultationId AND (g.dietPlanId IS NULL OR g.dietPlanId=NEW.id))
BEGIN SELECT RAISE(ABORT, 'Origin generation must match plan'); END;
CREATE TRIGGER DietPlan_consistent_generation_update BEFORE UPDATE OF generationId, consultationId ON DietPlan
WHEN (NEW.generationId IS NOT NULL AND NOT EXISTS (SELECT 1 FROM AIGeneration g WHERE g.id=NEW.generationId AND g.consultationId=NEW.consultationId AND (g.dietPlanId IS NULL OR g.dietPlanId=NEW.id)))
 OR EXISTS (SELECT 1 FROM AIGeneration g WHERE g.dietPlanId=OLD.id AND g.consultationId<>NEW.consultationId)
BEGIN SELECT RAISE(ABORT, 'Plan generation references must remain consistent'); END;

-- No author, approval date, AI generation or source is fabricated for legacy plans.
COMMIT;
PRAGMA foreign_keys=ON;

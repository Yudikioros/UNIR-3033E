-- Atomic, lossless decomposition of the phase 1 schema.
PRAGMA foreign_keys=OFF;
BEGIN TRANSACTION;
-- Fail atomically instead of dropping ambiguous structured values or inconsistent links.
CREATE TEMP TABLE normalization_preflight(ok INTEGER CHECK(ok=1));
WITH items AS (
 SELECT foodPreferences value FROM Patient UNION ALL SELECT foodsToAvoid FROM Patient
 UNION ALL SELECT allergiesOrIntolerances FROM Patient
 UNION ALL SELECT foodPreferences FROM NutritionConsultation
 UNION ALL SELECT foodsToAvoid FROM NutritionConsultation
 UNION ALL SELECT allergiesOrIntolerances FROM NutritionConsultation
)
INSERT INTO normalization_preflight
SELECT CASE WHEN EXISTS (
 SELECT 1 FROM items i,json_each(CASE WHEN json_valid(i.value) THEN CASE WHEN json_type(i.value)='array' THEN i.value ELSE '[]' END ELSE '[]' END) j
 WHERE j.type<>'text'
) THEN 0 ELSE 1 END;
INSERT INTO normalization_preflight
SELECT CASE WHEN EXISTS (
 SELECT 1 FROM DietPlan d JOIN AIGeneration g ON g.id=d.generationId
 WHERE g.consultationId<>d.consultationId OR (g.dietPlanId IS NOT NULL AND g.dietPlanId<>d.id)
) THEN 0 ELSE 1 END;
DROP TABLE normalization_preflight;
DROP TRIGGER DietPlan_consistent_patient_insert;
DROP TRIGGER DietPlan_consistent_patient_update;
DROP TRIGGER Consultation_consistent_patient_update;
DROP TRIGGER Generation_consistent_plan_insert;
DROP TRIGGER Generation_consistent_plan_update;
DROP TRIGGER DietPlan_consistent_generation_insert;
DROP TRIGGER DietPlan_consistent_generation_update;
-- CreateTable
CREATE TABLE "PatientDietaryItem" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "patientId" TEXT NOT NULL,
    "kind" TEXT NOT NULL CHECK (kind IN ('PREFERENCE','AVOID','ALLERGY_OR_INTOLERANCE')),
    "content" TEXT NOT NULL,
    CONSTRAINT "PatientDietaryItem_patientId_fkey" FOREIGN KEY ("patientId") REFERENCES "Patient" ("id") ON DELETE RESTRICT ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "ConsultationDietaryItem" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "consultationId" TEXT NOT NULL,
    "kind" TEXT NOT NULL CHECK (kind IN ('PREFERENCE','AVOID','ALLERGY_OR_INTOLERANCE')),
    "content" TEXT NOT NULL,
    CONSTRAINT "ConsultationDietaryItem_consultationId_fkey" FOREIGN KEY ("consultationId") REFERENCES "NutritionConsultation" ("id") ON DELETE RESTRICT ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "PatientCondition" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "patientId" TEXT NOT NULL,
    "description" TEXT NOT NULL,
    CONSTRAINT "PatientCondition_patientId_fkey" FOREIGN KEY ("patientId") REFERENCES "Patient" ("id") ON DELETE RESTRICT ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "ConsultationCalculation" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "consultationId" TEXT NOT NULL,
    "calculationMethod" TEXT,
    "calculationRuleVersion" TEXT,
    "calculationDetails" TEXT,
    "recordedAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "ConsultationCalculation_consultationId_fkey" FOREIGN KEY ("consultationId") REFERENCES "NutritionConsultation" ("id") ON DELETE RESTRICT ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "CalculationMetric" (
    "calculationId" TEXT NOT NULL,
    "metricCode" TEXT NOT NULL,
    "value" REAL NOT NULL,

    PRIMARY KEY ("calculationId", "metricCode"),
    CONSTRAINT "CalculationMetric_calculationId_fkey" FOREIGN KEY ("calculationId") REFERENCES "ConsultationCalculation" ("id") ON DELETE RESTRICT ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "PlanNutrientObservation" (
    "dietPlanId" TEXT NOT NULL,
    "metricCode" TEXT NOT NULL,
    "value" REAL NOT NULL,

    PRIMARY KEY ("dietPlanId", "metricCode"),
    CONSTRAINT "PlanNutrientObservation_dietPlanId_fkey" FOREIGN KEY ("dietPlanId") REFERENCES "DietPlan" ("id") ON DELETE RESTRICT ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "GenerationPlanLink" (
    "generationId" TEXT NOT NULL PRIMARY KEY,
    "dietPlanId" TEXT NOT NULL,
    "isOrigin" BOOLEAN NOT NULL DEFAULT false,
    CONSTRAINT "GenerationPlanLink_generationId_fkey" FOREIGN KEY ("generationId") REFERENCES "AIGeneration" ("id") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "GenerationPlanLink_dietPlanId_fkey" FOREIGN KEY ("dietPlanId") REFERENCES "DietPlan" ("id") ON DELETE RESTRICT ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "LegacyPatientSnapshot" (
    "patientId" TEXT NOT NULL PRIMARY KEY,
    "originalGoal" TEXT NOT NULL,
    "originalPathologies" TEXT NOT NULL,
    "originalPreferences" TEXT,
    "originalFoodsToAvoid" TEXT,
    "originalAllergies" TEXT,
    "importedAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "LegacyPatientSnapshot_patientId_fkey" FOREIGN KEY ("patientId") REFERENCES "Patient" ("id") ON DELETE RESTRICT ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "LegacyPlanSnapshot" (
    "dietPlanId" TEXT NOT NULL PRIMARY KEY,
    "originalPatientId" TEXT NOT NULL,
    "originalTdee" REAL,
    "originalPlanJson" TEXT,
    "originalStatus" TEXT,
    "importedAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "LegacyPlanSnapshot_dietPlanId_fkey" FOREIGN KEY ("dietPlanId") REFERENCES "DietPlan" ("id") ON DELETE RESTRICT ON UPDATE CASCADE
);

-- Preserve original documents as immutable provenance before removing old columns.
INSERT INTO LegacyPatientSnapshot(patientId,originalGoal,originalPathologies,originalPreferences,originalFoodsToAvoid,originalAllergies)
SELECT id,goal,pathologies,foodPreferences,foodsToAvoid,allergiesOrIntolerances FROM Patient;
INSERT INTO LegacyPlanSnapshot(dietPlanId,originalPatientId,originalTdee,originalPlanJson,originalStatus)
SELECT id,patientId,tdee_calculated,plan_json,COALESCE(legacyStatus,status) FROM DietPlan;
INSERT INTO PatientCondition(id,patientId,description)
SELECT 'legacy-condition-'||id,id,pathologies FROM Patient WHERE trim(pathologies)<>'';

-- JSON arrays become individual facts; free text remains a single narrative fact.
WITH items AS (
 SELECT id,'PREFERENCE' kind,foodPreferences value FROM Patient UNION ALL
 SELECT id,'AVOID',foodsToAvoid FROM Patient UNION ALL
 SELECT id,'ALLERGY_OR_INTOLERANCE',allergiesOrIntolerances FROM Patient
), expanded AS (
 SELECT i.id,i.kind,j.value content FROM items i,
 json_each(CASE WHEN json_valid(i.value) THEN CASE WHEN json_type(i.value)='array' THEN i.value ELSE json_array(i.value) END ELSE json_array(i.value) END) j
 WHERE j.type='text' AND trim(j.value)<>''
)
INSERT INTO PatientDietaryItem(id,patientId,kind,content)
SELECT lower(hex(randomblob(16))),id,kind,content FROM expanded GROUP BY id,kind,content;
WITH items AS (
 SELECT id,'PREFERENCE' kind,foodPreferences value FROM NutritionConsultation UNION ALL
 SELECT id,'AVOID',foodsToAvoid FROM NutritionConsultation UNION ALL
 SELECT id,'ALLERGY_OR_INTOLERANCE',allergiesOrIntolerances FROM NutritionConsultation
), expanded AS (
 SELECT i.id,i.kind,j.value content FROM items i,
 json_each(CASE WHEN json_valid(i.value) THEN CASE WHEN json_type(i.value)='array' THEN i.value ELSE json_array(i.value) END ELSE json_array(i.value) END) j
 WHERE j.type='text' AND trim(j.value)<>''
)
INSERT INTO ConsultationDietaryItem(id,consultationId,kind,content)
SELECT lower(hex(randomblob(16))),id,kind,content FROM expanded GROUP BY id,kind,content;

INSERT INTO ConsultationCalculation(id,consultationId,calculationMethod,calculationRuleVersion,calculationDetails,recordedAt)
SELECT 'legacy-calculation-'||id,id,calculationMethod,calculationRuleVersion,calculationDetails,updatedAt
FROM NutritionConsultation WHERE COALESCE(calculationMethod,calculationRuleVersion,calculationDetails,bmi,basalMetabolicRate,totalEnergyExpenditure,targetCalories,proteinGrams,carbohydrateGrams,fatGrams,fiberGrams,waterLiters) IS NOT NULL;
WITH metrics AS (
 SELECT id,'bmi' code,bmi value FROM NutritionConsultation UNION ALL
 SELECT id,'basalMetabolicRate',basalMetabolicRate FROM NutritionConsultation UNION ALL
 SELECT id,'totalEnergyExpenditure',totalEnergyExpenditure FROM NutritionConsultation UNION ALL
 SELECT id,'targetCalories',targetCalories FROM NutritionConsultation UNION ALL
 SELECT id,'proteinGrams',proteinGrams FROM NutritionConsultation UNION ALL
 SELECT id,'carbohydrateGrams',carbohydrateGrams FROM NutritionConsultation UNION ALL
 SELECT id,'fatGrams',fatGrams FROM NutritionConsultation UNION ALL
 SELECT id,'fiberGrams',fiberGrams FROM NutritionConsultation UNION ALL
 SELECT id,'waterLiters',waterLiters FROM NutritionConsultation
)
INSERT INTO CalculationMetric(calculationId,metricCode,value)
SELECT 'legacy-calculation-'||id,code,value FROM metrics WHERE value IS NOT NULL;
WITH metrics AS (
 SELECT id,'totalCalories' code,totalCalories value FROM DietPlan UNION ALL
 SELECT id,'proteinGrams',proteinGrams FROM DietPlan UNION ALL
 SELECT id,'carbohydrateGrams',carbohydrateGrams FROM DietPlan UNION ALL
 SELECT id,'fatGrams',fatGrams FROM DietPlan UNION ALL
 SELECT id,'fiberGrams',fiberGrams FROM DietPlan UNION ALL
 SELECT id,'waterLiters',waterLiters FROM DietPlan
)
INSERT INTO PlanNutrientObservation(dietPlanId,metricCode,value)
SELECT id,code,value FROM metrics WHERE value IS NOT NULL;
INSERT INTO GenerationPlanLink(generationId,dietPlanId,isOrigin)
SELECT id,dietPlanId,0 FROM AIGeneration WHERE dietPlanId IS NOT NULL;
INSERT INTO GenerationPlanLink(generationId,dietPlanId,isOrigin)
SELECT generationId,id,1 FROM DietPlan WHERE generationId IS NOT NULL
ON CONFLICT(generationId) DO UPDATE SET isOrigin=1;

-- Canonical operational goal; the source spelling remains in the archive.
UPDATE Patient SET defaultGoal=COALESCE(defaultGoal,CASE goal
 WHEN 'Pérdida de peso' THEN 'WEIGHT_LOSS' WHEN 'Mantenimiento' THEN 'MAINTENANCE'
 WHEN 'Ganancia muscular' THEN 'WEIGHT_GAIN' WHEN 'Ganancia de peso' THEN 'WEIGHT_GAIN'
 ELSE NULLIF(goal,'') END);
-- RedefineTables
CREATE TABLE "new_Patient" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "name" TEXT NOT NULL DEFAULT 'Paciente Nuevo',
    "birthDate" DATETIME,
    "age" INTEGER CHECK (birthDate IS NULL OR age IS NULL),
    "ageRecordedAt" DATETIME,
    "gender" TEXT NOT NULL,
    "email" TEXT,
    "phone" TEXT,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "defaultActivityLevel" TEXT,
    "defaultGoal" TEXT,
    "defaultMealsPerDay" INTEGER,
    "defaultDailyBudget" REAL,
    "notes" TEXT,
    "demoKey" TEXT
);
INSERT INTO "new_Patient" ("age", "birthDate", "createdAt", "defaultActivityLevel", "defaultDailyBudget", "defaultGoal", "defaultMealsPerDay", "demoKey", "email", "gender", "id", "name", "notes", "phone", "updatedAt") SELECT "age", "birthDate", "createdAt", "defaultActivityLevel", "defaultDailyBudget", "defaultGoal", "defaultMealsPerDay", "demoKey", "email", "gender", "id", "name", "notes", "phone", "updatedAt" FROM "Patient";
DROP TABLE "Patient";
ALTER TABLE "new_Patient" RENAME TO "Patient";
UPDATE Patient SET ageRecordedAt=CURRENT_TIMESTAMP WHERE age IS NOT NULL;
CREATE UNIQUE INDEX "Patient_demoKey_key" ON "Patient"("demoKey");
CREATE TABLE "new_NutritionConsultation" (
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
    "notes" TEXT,
    "legacyPlanId" TEXT,
    "demoKey" TEXT,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "NutritionConsultation_patientId_fkey" FOREIGN KEY ("patientId") REFERENCES "Patient" ("id") ON DELETE RESTRICT ON UPDATE CASCADE
);
INSERT INTO "new_NutritionConsultation" ("activityLevel", "ageAtConsultation", "budgetMax", "budgetMin", "consultationDate", "createdAt", "dailyBudget", "demoKey", "goal", "heightM", "id", "legacyPlanId", "mealsPerDay", "notes", "patientId", "sex", "updatedAt", "weightKg") SELECT "activityLevel", "ageAtConsultation", "budgetMax", "budgetMin", "consultationDate", "createdAt", "dailyBudget", "demoKey", "goal", "heightM", "id", "legacyPlanId", "mealsPerDay", "notes", "patientId", "sex", "updatedAt", "weightKg" FROM "NutritionConsultation";
DROP TABLE "NutritionConsultation";
ALTER TABLE "new_NutritionConsultation" RENAME TO "NutritionConsultation";
CREATE UNIQUE INDEX "NutritionConsultation_legacyPlanId_key" ON "NutritionConsultation"("legacyPlanId");
CREATE UNIQUE INDEX "NutritionConsultation_demoKey_key" ON "NutritionConsultation"("demoKey");
CREATE INDEX "NutritionConsultation_patientId_idx" ON "NutritionConsultation"("patientId");
CREATE INDEX "NutritionConsultation_consultationDate_idx" ON "NutritionConsultation"("consultationDate");
CREATE TABLE "new_DietPlan" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "consultationId" TEXT NOT NULL,
    "version" INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    "status" TEXT NOT NULL DEFAULT 'DRAFT' CHECK (status IN ('DRAFT','UNDER_REVIEW','MODIFIED','REGENERATED','REJECTED','APPROVED')),
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "approvedAt" DATETIME,
    "approvedBy" TEXT,
    "rejectedAt" DATETIME,
    "rejectedBy" TEXT,
    "rejectionReason" TEXT,
    CONSTRAINT "DietPlan_consultationId_fkey" FOREIGN KEY ("consultationId") REFERENCES "NutritionConsultation" ("id") ON DELETE RESTRICT ON UPDATE CASCADE
);
INSERT INTO "new_DietPlan" ("approvedAt", "approvedBy", "consultationId", "createdAt", "id", "rejectedAt", "rejectedBy", "rejectionReason", "status", "updatedAt", "version") SELECT "approvedAt", "approvedBy", "consultationId", "createdAt", "id", "rejectedAt", "rejectedBy", "rejectionReason", "status", "updatedAt", "version" FROM "DietPlan";
DROP TABLE "DietPlan";
ALTER TABLE "new_DietPlan" RENAME TO "DietPlan";
CREATE INDEX "DietPlan_consultationId_idx" ON "DietPlan"("consultationId");
CREATE INDEX "DietPlan_status_idx" ON "DietPlan"("status");
CREATE UNIQUE INDEX "DietPlan_consultationId_version_key" ON "DietPlan"("consultationId", "version");
CREATE TABLE "new_AIGeneration" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "consultationId" TEXT NOT NULL,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "modelProvider" TEXT NOT NULL,
    "modelName" TEXT NOT NULL,
    "modelVersion" TEXT,
    "promptVersion" TEXT,
    "knowledgeBaseVersion" TEXT,
    "executionTimeMs" INTEGER CHECK (executionTimeMs IS NULL OR executionTimeMs >= 0),
    "status" TEXT NOT NULL,
    "errorMessage" TEXT,
    "retainPayloads" BOOLEAN NOT NULL DEFAULT false,
    "requestPayload" TEXT,
    "responsePayload" TEXT,
    CHECK (retainPayloads OR (requestPayload IS NULL AND responsePayload IS NULL)),
    CONSTRAINT "AIGeneration_consultationId_fkey" FOREIGN KEY ("consultationId") REFERENCES "NutritionConsultation" ("id") ON DELETE RESTRICT ON UPDATE CASCADE
);
INSERT INTO "new_AIGeneration" ("consultationId", "createdAt", "errorMessage", "executionTimeMs", "id", "knowledgeBaseVersion", "modelName", "modelProvider", "modelVersion", "promptVersion", "requestPayload", "responsePayload", "retainPayloads", "status") SELECT "consultationId", "createdAt", "errorMessage", "executionTimeMs", "id", "knowledgeBaseVersion", "modelName", "modelProvider", "modelVersion", "promptVersion", "requestPayload", "responsePayload", "retainPayloads", "status" FROM "AIGeneration";
DROP TABLE "AIGeneration";
ALTER TABLE "new_AIGeneration" RENAME TO "AIGeneration";
CREATE INDEX "AIGeneration_consultationId_idx" ON "AIGeneration"("consultationId");
CREATE INDEX "AIGeneration_createdAt_idx" ON "AIGeneration"("createdAt");

-- CreateIndex
CREATE UNIQUE INDEX "PatientDietaryItem_patientId_kind_content_key" ON "PatientDietaryItem"("patientId", "kind", "content");

-- CreateIndex
CREATE UNIQUE INDEX "ConsultationDietaryItem_consultationId_kind_content_key" ON "ConsultationDietaryItem"("consultationId", "kind", "content");

-- CreateIndex
CREATE UNIQUE INDEX "PatientCondition_patientId_description_key" ON "PatientCondition"("patientId", "description");

-- CreateIndex
CREATE INDEX "ConsultationCalculation_consultationId_recordedAt_idx" ON "ConsultationCalculation"("consultationId", "recordedAt");

-- CreateIndex
CREATE INDEX "GenerationPlanLink_dietPlanId_idx" ON "GenerationPlanLink"("dietPlanId");
CREATE UNIQUE INDEX GenerationPlanLink_one_origin ON GenerationPlanLink(dietPlanId) WHERE isOrigin=1;

CREATE TRIGGER GenerationPlanLink_consistent_insert BEFORE INSERT ON GenerationPlanLink
WHEN NOT EXISTS (SELECT 1 FROM AIGeneration g JOIN DietPlan d ON d.consultationId=g.consultationId WHERE g.id=NEW.generationId AND d.id=NEW.dietPlanId)
BEGIN SELECT RAISE(ABORT,'Generation and plan must belong to the same consultation'); END;
CREATE TRIGGER GenerationPlanLink_consistent_update BEFORE UPDATE ON GenerationPlanLink
WHEN NOT EXISTS (SELECT 1 FROM AIGeneration g JOIN DietPlan d ON d.consultationId=g.consultationId WHERE g.id=NEW.generationId AND d.id=NEW.dietPlanId)
BEGIN SELECT RAISE(ABORT,'Generation and plan must belong to the same consultation'); END;
CREATE TRIGGER Generation_consultation_update BEFORE UPDATE OF consultationId ON AIGeneration
WHEN EXISTS (SELECT 1 FROM GenerationPlanLink l JOIN DietPlan d ON d.id=l.dietPlanId WHERE l.generationId=OLD.id AND d.consultationId<>NEW.consultationId)
BEGIN SELECT RAISE(ABORT,'Generation consultation conflicts with linked plan'); END;
CREATE TRIGGER Plan_consultation_update BEFORE UPDATE OF consultationId ON DietPlan
WHEN EXISTS (SELECT 1 FROM GenerationPlanLink l JOIN AIGeneration g ON g.id=l.generationId WHERE l.dietPlanId=OLD.id AND g.consultationId<>NEW.consultationId)
BEGIN SELECT RAISE(ABORT,'Plan consultation conflicts with linked generation'); END;

CREATE TRIGGER LegacyPatientSnapshot_no_update BEFORE UPDATE ON LegacyPatientSnapshot
BEGIN SELECT RAISE(ABORT,'Source snapshot is immutable'); END;
CREATE TRIGGER LegacyPatientSnapshot_no_delete BEFORE DELETE ON LegacyPatientSnapshot
BEGIN SELECT RAISE(ABORT,'Source snapshot is immutable'); END;
CREATE TRIGGER LegacyPlanSnapshot_no_update BEFORE UPDATE ON LegacyPlanSnapshot
BEGIN SELECT RAISE(ABORT,'Source snapshot is immutable'); END;
CREATE TRIGGER LegacyPlanSnapshot_no_delete BEFORE DELETE ON LegacyPlanSnapshot
BEGIN SELECT RAISE(ABORT,'Source snapshot is immutable'); END;
COMMIT;
PRAGMA foreign_keys=ON;

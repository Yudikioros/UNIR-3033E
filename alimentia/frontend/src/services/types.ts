export type Sex = "female" | "male";
export type ActivityLevel = "sedentary" | "light" | "moderate" | "active" | "very active";
export type Goal = "WEIGHT_LOSS" | "MAINTENANCE" | "WEIGHT_GAIN";
export type ConsultationStatus = "DRAFT" | "READY";
export type PlanStatus = "DRAFT" | "UNDER_REVIEW" | "MODIFIED" | "REGENERATED" | "REJECTED" | "APPROVED";

export interface PatientCreate {
  name: string;
  sex: Sex;
  birthDate?: string | null;
  age?: number | null;
  email?: string | null;
  phone?: string | null;
  defaultActivityLevel?: ActivityLevel | null;
  defaultGoal?: Goal | null;
  defaultMealsPerDay?: number | null;
  defaultDailyBudget?: number | null;
  foodPreferences?: string | null;
  foodsToAvoid?: string | null;
  allergiesOrIntolerances?: string | null;
  notes?: string | null;
}
export type PatientUpdate = Partial<PatientCreate> & { expectedUpdatedAt?: string };
export interface PlanSummary { id: string; version: number; status: PlanStatus }
export interface Patient extends Omit<PatientCreate, "defaultGoal" | "defaultActivityLevel"> {
  id: string;
  createdAt: string;
  updatedAt: string;
  defaultGoal: string | null;
  defaultActivityLevel: string | null;
  currentAge: number | null;
  conditions: string[];
  latestConsultationDate: string | null;
  latestPlan: PlanSummary | null;
  isDemo: boolean;
}
export interface ConsultationCreate {
  consultationDate?: string | null;
  ageAtConsultation?: number | null;
  sex?: Sex | null;
  weightKg?: number | null;
  heightM?: number | null;
  activityLevel?: ActivityLevel | null;
  goal?: Goal | null;
  mealsPerDay?: number | null;
  dailyBudget?: number | null;
  budgetMin?: number | null;
  budgetMax?: number | null;
  foodPreferences?: string | null;
  foodsToAvoid?: string | null;
  allergiesOrIntolerances?: string | null;
  notes?: string | null;
  requiresProfessionalReview?: boolean;
  status?: ConsultationStatus;
}
export type ConsultationUpdate = ConsultationCreate & { expectedUpdatedAt?: string };
export interface Consultation extends Omit<Required<ConsultationCreate>, "goal" | "activityLevel" | "sex"> {
  id: string;
  patientId: string;
  createdAt: string;
  updatedAt: string;
  consultationDate: string;
  sex: string | null;
  goal: string | null;
  activityLevel: string | null;
  isEditable: boolean;
  readinessIssues: string[];
  scopeWarning: string | null;
  plans: PlanSummary[];
  // Motor de cálculo determinístico (Fase 3). Null hasta el primer cálculo.
  calculationMethod: string | null;
  calculationRuleVersion: string | null;
  calculationDetails: string | null;
  bmi: number | null;
  basalMetabolicRate: number | null;
  totalEnergyExpenditure: number | null;
  targetCalories: number | null;
  proteinGrams: number | null;
  carbohydrateGrams: number | null;
  fatGrams: number | null;
  fiberGrams: number | null;
  waterLiters: number | null;
}
export interface Option<T extends string = string> { value: T; label: string }
export interface FieldLimits { minimum?: number; maximum?: number; exclusiveMinimum?: number; minLength?: number; maxLength?: number }
export interface CaptureOptions {
  scopeWarning: string;
  sex: Option<Sex>[];
  activity: Option<ActivityLevel>[];
  goal: Option<Goal>[];
  patientLimits: Record<string, FieldLimits>;
  consultationLimits: Record<string, FieldLimits>;
}
export type SourceType = "GUIDELINE" | "REFERENCE_TABLE" | "REGULATION" | "OTHER";
// Administración de documentos: estado real de indexación en Qdrant (nunca
// se muestra "Vigente" solo porque existe la fila en KnowledgeSource).
export type IndexStatus = "INDEXING" | "INDEXED" | "ERROR";
export interface KnowledgeSource {
  id: string;
  documentName: string;
  institution: string | null;
  version: string | null;
  publicationDate: string | null;
  sourceType: SourceType | null;
  isActive: boolean;
  originalFilename: string | null;
  checksum: string | null;
  createdAt: string;
  updatedAt: string;
  manifestSourceId: string | null;
  indexStatus: IndexStatus;
  indexError: string | null;
}
export interface KnowledgeSourceCreate {
  file: File;
  name: string;
  institution?: string;
  version?: string;
  sourceType: SourceType;
  publicationDate?: string;
}
export interface DietPlanFood {
  id: string;
  foodName: string;
  quantity: number | null;
  unit: string | null;
  smaeEquivalent: string | null;
  calories: number | null;
  protein: number | null;
  carbohydrates: number | null;
  fat: number | null;
  notes: string | null;
  legacyQuantity: string | null;
}
export interface DietPlanMeal {
  id: string;
  mealType: string;
  name: string;
  sortOrder: number;
  foods: DietPlanFood[];
}
export interface DietPlan {
  id: string;
  consultationId: string;
  version: number;
  status: PlanStatus;
  totalCalories: number | null;
  proteinGrams: number | null;
  carbohydrateGrams: number | null;
  fatGrams: number | null;
  fiberGrams: number | null;
  waterLiters: number | null;
  approvedAt: string | null;
  approvedBy: string | null;
  rejectedAt: string | null;
  rejectedBy: string | null;
  rejectionReason: string | null;
  generationId: string | null;
  summary: string | null;
  recommendations: string[];
  createdAt: string;
  updatedAt: string;
  meals: DietPlanMeal[];
}
export type ValidationSeverity = "INFO" | "WARNING" | "ERROR";
export interface PlanValidation {
  id: string;
  severity: ValidationSeverity;
  code: string;
  message: string;
  source: string;
  isBlocking: boolean;
  createdAt: string;
}
export interface RetrievedSource {
  id: string;
  knowledgeSourceId: string;
  documentName: string;
  institution: string | null;
  section: string | null;
  retrievalScore: number | null;
}
export interface DietPlanDetail extends DietPlan {
  targetCalories: number | null;
  targetProteinGrams: number | null;
  targetCarbohydrateGrams: number | null;
  targetFatGrams: number | null;
  targetFiberGrams: number | null;
  targetWaterLiters: number | null;
  validations: PlanValidation[];
  sources: RetrievedSource[];
  blockingValidationCount: number;
  isEditable: boolean;
  generatedAt: string | null;
  modelProvider: string | null;
  modelName: string | null;
  promptVersion: string | null;
  knowledgeBaseVersion: string | null;
}
export interface DietPlanFoodEdit {
  foodName: string;
  quantity: number;
  unit: string;
  smaeEquivalent?: string | null;
  calories?: number | null;
  protein?: number | null;
  carbohydrates?: number | null;
  fat?: number | null;
  notes?: string | null;
}
export interface DietPlanMealEdit {
  mealType: string;
  name: string;
  foods: DietPlanFoodEdit[];
}
export interface DietPlanEditRequest {
  meals: DietPlanMealEdit[];
  actor?: string | null;
  expectedUpdatedAt?: string;
}
export interface DietPlanGenerationResult {
  generationId: string;
  dietPlanId: string | null;
  version: number | null;
  status: string;
  plan: DietPlan | null;
  validations: PlanValidation[];
  sources: RetrievedSource[];
  foodDatabaseUsed: boolean;
  knowledgeBaseUsed: boolean;
}
// Progreso por etapas real (corrección de UX): estos valores reflejan
// exactamente los estados que puede reportar el backend, nunca una
// animación o temporizador ficticio del lado del cliente.
export type GenerationStage =
  | "VALIDATING" | "LOADING_CALCULATIONS" | "LOADING_FOOD_DATA" | "SEARCHING_KNOWLEDGE"
  | "BUILDING_CONTEXT" | "GENERATING_WITH_LLM" | "VALIDATING_RESPONSE" | "PERSISTING"
  | "COMPLETED" | "FAILED";
export type GenerationJobStatus = "IN_PROGRESS" | "SUCCESS" | "FAILED";
export interface GenerationJobStarted {
  generationId: string;
}
export interface GenerationStatus {
  generationId: string;
  consultationId: string;
  status: GenerationJobStatus;
  stage: GenerationStage | null;
  startedAt: string;
  completedAt: string | null;
  errorMessage: string | null;
  dietPlanId: string | null;
}
// Resumen operativo (`/`): cada campo se corresponde 1:1 con una consulta
// real en backend (app.repositories.dashboard) -nunca un mock/placeholder.
export interface DashboardMetrics {
  registeredPatients: number;
  generatedPlans: number;
  pendingReview: number;
  approvedPlans: number;
  averageReviewTimeSeconds: number | null;
}
export interface DashboardPatientRow {
  id: string;
  name: string;
  currentAge: number | null;
  isDemo: boolean;
  goal: string | null;
  latestConsultationDate: string | null;
  latestPlanId: string | null;
  latestPlanVersion: number | null;
  latestPlanStatus: PlanStatus | null;
}
export interface DashboardPendingPlan {
  planId: string;
  patientId: string;
  patientName: string;
  version: number;
  status: PlanStatus;
  generatedAt: string | null;
}
export interface DashboardSummary {
  metrics: DashboardMetrics;
  recentPatients: DashboardPatientRow[];
  pendingPlans: DashboardPendingPlan[];
  pendingPlansTotal: number;
}
export interface PlanTraceability {
  plan: { id: string; version: number; status: string };
  calculation: { calculationId: string | null; method: string | null; rulesetVersion: string | null; recordedAt: string | null };
  generation: {
    generationId: string | null; modelProvider: string | null; modelName: string | null;
    promptVersion: string | null; generationDurationMs: number | null; knowledgeBaseVersion: string | null;
  };
  resources: {
    foodDatabaseUsed: boolean | null; foodDatabaseName: string | null;
    foodDatabaseVersion: string | null; knowledgeBaseUsed: boolean | null;
  };
  sources: { sourceId: string; name: string; version: string | null; document: string | null }[];
  humanReview: {
    manualEditCount: number; regenerationCount: number;
    approvedAt: string | null; approvedBy: string | null; rejectedAt: string | null; rejectedBy: string | null;
  };
  validations: { code: string; severity: ValidationSeverity; isBlocking: boolean; message: string }[];
}
export interface EvaluationMetrics {
  consultationId: string;
  planId: string;
  generationCount: number;
  regenerationCount: number;
  manualEditCount: number;
  versionCount: number;
  initialPlanVersion: number | null;
  finalPlanVersion: number | null;
  approvedVersion: number | null;
  generationDurationMs: number | null;
  timeFromFirstGenerationToApprovalSeconds: number | null;
  initialEnergyDeviationPercent: number | null;
  finalEnergyDeviationPercent: number | null;
  initialBlockingValidationCount: number | null;
  finalBlockingValidationCount: number | null;
  initialMealCount: number | null;
  finalMealCount: number | null;
  knowledgeBaseUsed: boolean | null;
  foodDatabaseUsed: boolean | null;
  retrievedSourceCount: number;
  modelName: string | null;
  promptVersion: string | null;
  calculationRuleVersion: string | null;
}
export interface AssistantNavigationContext {
  route?: string | null;
  patientId?: string | null;
  consultationId?: string | null;
  planId?: string | null;
}
export interface AssistantConversationTurn { role: "user" | "assistant"; content: string }
export interface AssistantChatRequest {
  message: string;
  context?: AssistantNavigationContext;
  conversation?: AssistantConversationTurn[];
}
export interface AssistantSourceCitation { sourceId: string; documentName: string; institution: string | null }
export interface AssistantChatResponse {
  answer: string;
  toolsUsed: string[];
  sources: AssistantSourceCitation[];
  structuredData: Record<string, unknown> | null;
  metadata: { model: string; promptVersion: string; executionTimeMs: number; toolIterations: number };
}
export interface LegacyPlan {
  id: string;
  createdAt: string;
  status: string;
  tdee_calculated: number | null;
  patient: { id: string; name: string };
}

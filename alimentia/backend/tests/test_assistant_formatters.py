"""
Pruebas de los builders de texto determinísticos (sección 12 de la
corrección). Construyen los DTOs a mano -sin tocar la base de datos ni el
LLM- y verifican que el texto producido refleje exactamente los datos dados,
nunca datos inventados.
"""
import unittest
from datetime import datetime

from app.schemas.assistant import (
    AssistantCalculationDetail, AssistantPatientRef, AssistantPatientSummary, AssistantPlanDetail,
    AssistantPlanSummary, AssistantValidation, PatientPlanStatusRef, PlanStatusCount,
)
from app.services import assistant_formatters as fmt


class FormatterTests(unittest.TestCase):
    def test_patient_not_found(self):
        self.assertIn("María", fmt.format_patient_not_found("María"))

    def test_multiple_patients_lista_todos_los_nombres(self):
        matches = [AssistantPatientRef(id="1", name="María González"), AssistantPatientRef(id="2", name="María Pérez")]
        text = fmt.format_multiple_patients("María", matches)
        self.assertIn("María González", text)
        self.assertIn("María Pérez", text)

    def test_patient_summary_incluye_edad_y_objetivo(self):
        patient = AssistantPatientSummary(id="1", name="Ana Torres", currentAge=30, defaultGoal="WEIGHT_LOSS",
            conditions=["diabetes"])
        text = fmt.format_patient_summary(patient)
        self.assertIn("Ana Torres", text)
        self.assertIn("30", text)
        self.assertIn("diabetes", text)

    def test_patient_plans_vacio(self):
        text = fmt.format_patient_plans("Ana Torres", [])
        self.assertIn("todavía no tiene ningún plan", text)

    def test_patient_plans_con_energia(self):
        plans = [AssistantPlanSummary(id="p1", consultationId="c1", version=1, status="APPROVED",
            totalCalories=1800, createdAt=datetime(2026, 1, 1))]
        text = fmt.format_patient_plans("Ana Torres", plans)
        self.assertIn("1800", text)
        self.assertIn("aprobado", text)

    def test_calculation_summary_incluye_macros(self):
        calc = AssistantCalculationDetail(consultationId="c1", calculationMethod="MIFFLIN_ST_JEOR",
            calculationRuleVersion="1.0", basalMetabolicRate=1400, totalEnergyExpenditure=2000,
            targetCalories=1700, proteinGrams=90, carbohydrateGrams=180, fatGrams=55)
        text = fmt.format_calculation_summary("Ana Torres", calc)
        self.assertIn("1700", text)
        self.assertIn("90", text)

    def _plan(self, **overrides) -> AssistantPlanDetail:
        base = dict(id="p1", consultationId="c1", version=1, status="UNDER_REVIEW", isEditable=True,
            createdAt=datetime(2026, 1, 1), totalCalories=1800, targetCalories=1800, blockingValidationCount=0,
            validations=[])
        base.update(overrides)
        return AssistantPlanDetail(**base)

    def test_plan_approval_status_sin_bloqueantes(self):
        plan = self._plan()
        text = fmt.format_plan_approval_status(plan)
        self.assertIn("puede aprobarse", text)

    def test_plan_approval_status_con_bloqueantes_nunca_dice_que_puede_aprobarse(self):
        validation = AssistantValidation(code="ENERGY_OUT_OF_TOLERANCE", severity="ERROR",
            message="La energía total excede la tolerancia permitida.", isBlocking=True)
        plan = self._plan(blockingValidationCount=1, validations=[validation])
        text = fmt.format_plan_approval_status(plan)
        self.assertIn("no puede aprobarse todavía", text)
        self.assertIn("La energía total excede", text)

    def test_plan_approval_status_ya_aprobado(self):
        plan = self._plan(status="APPROVED")
        self.assertIn("ya está aprobado", fmt.format_plan_approval_status(plan))

    def test_plan_approval_status_rechazado_incluye_motivo(self):
        plan = self._plan(status="REJECTED", rejectionReason="Faltan alimentos de origen animal.")
        text = fmt.format_plan_approval_status(plan)
        self.assertIn("rechazado", text)
        self.assertIn("Faltan alimentos", text)

    def test_plan_counts(self):
        counts = [PlanStatusCount(status="APPROVED", count=3), PlanStatusCount(status="DRAFT", count=1)]
        text = fmt.format_plan_counts(counts)
        self.assertIn("3", text)
        self.assertIn("aprobado", text)

    def test_patients_by_status_deduplica_pacientes(self):
        rows = [PatientPlanStatusRef(patientId="1", patientName="Ana", planId="p1", version=1, status="APPROVED"),
                PatientPlanStatusRef(patientId="1", patientName="Ana", planId="p2", version=2, status="APPROVED")]
        text = fmt.format_patients_by_status("APPROVED", rows)
        self.assertEqual(text.count("Ana"), 1)


if __name__ == "__main__":
    unittest.main()

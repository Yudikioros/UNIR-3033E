"""
Exportación de plan APROBADO a PDF (Fase 6, Parte D).

Solo un DietPlan en estado APPROVED puede exportarse como documento final
(ver `routes/plans.py`). El PDF es un documento clínico legible por el
paciente y el profesional: nunca incluye UUIDs, prompts, logs, scores de
embeddings, nombres técnicos de tablas ni metadata interna de la API.
"""
from datetime import datetime

from fpdf import FPDF
from fpdf.errors import FPDFException

GOAL_LABELS = {"WEIGHT_LOSS": "Pérdida de peso", "MAINTENANCE": "Mantenimiento", "WEIGHT_GAIN": "Incremento de peso"}

# La fuente core "helvetica" del PDF solo soporta Latin-1/WinAnsi (incluye
# acentos y ¿/¡ del español). El resumen, las recomendaciones y las notas por
# alimento vienen del LLM (texto no controlado): sin sanear, un guion largo,
# comillas tipográficas o una viñeta que el modelo genere haría fallar toda
# la exportación con un 500 en vez de producir el PDF.
_CHAR_FALLBACKS = {
    "—": "-", "–": "-", "‘": "'", "’": "'",
    "“": '"', "”": '"', "…": "...", "•": "-",
    "≈": "~", " ": " ",
}


def _safe(value) -> str:
    if value is None:
        return ""
    return "".join(ch if ord(ch) <= 255 else _CHAR_FALLBACKS.get(ch, "?") for ch in str(value))


def _num(value, decimals=0):
    if value is None:
        return "-"
    return f"{value:.{decimals}f}"


def _date(value: datetime | None) -> str:
    return value.strftime("%d/%m/%Y") if value else "-"


def _quantity(value):
    if value is None:
        return "-"
    return f"{value:g}"


def _multi_cell(pdf, h, text, indent=0, **kwargs):
    """`multi_cell` con sangría opcional y recuperación defensiva.

    fpdf2 puede lanzar `FPDFException("Not enough horizontal space...")` por
    un cálculo de ancho disponible que falla cerca de un salto de página
    automático, incluso con texto corto y bien formado (reproducido con datos
    reales de esta app, no solo con texto exótico). Forzar una página nueva
    y reintentar una vez basta para producir el PDF de todas formas: la
    exportación nunca debe responder 500 por esto.

    Siempre fija `x` al margen (+ sangría) antes de escribir: `multi_cell` dejA
    `x` donde empezó la celda, no en el margen izquierdo, así que sin esto la
    siguiente línea heredaría una posición y un ancho disponible incorrectos.
    """
    pdf.set_x(pdf.l_margin + indent)
    try:
        pdf.multi_cell(0, h, text, **kwargs)
    except FPDFException:
        pdf.add_page()
        pdf.set_x(pdf.l_margin + indent)
        pdf.multi_cell(0, h, text, **kwargs)
    pdf.set_x(pdf.l_margin)


class _PlanPDF(FPDF):
    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 7)
        self.set_text_color(140, 140, 140)
        self.cell(0, 10, "Generado por AlimentIA. Este documento es un plan de referencia; "
                          "cualquier duda debe consultarse con el profesional responsable.", align="C")


def build_plan_pdf(*, plan, consultation, patient_name: str, sources: list) -> bytes:
    """`plan`: DietPlanDetail (Fase 5). `consultation`: NutritionConsultationRead (Fase 1).
    `sources`: RetrievedSourceRead[] realmente recuperados/persistidos para ESTE plan.
    """
    pdf = _PlanPDF(format="A4", unit="mm")
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 10, "AlimentIA", ln=True)
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(90, 90, 90)
    pdf.cell(0, 6, "Plan alimentario", ln=True)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(3)

    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 6, f"Paciente: {_safe(patient_name)}", ln=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, f"Fecha de emisión: {_date(datetime.now())}    Versión: {plan.version}", ln=True)
    pdf.set_text_color(20, 120, 40)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 6, "Estado: APROBADO", ln=True)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "", 10)
    approval_line = f"Aprobado por: {_safe(plan.approvedBy) or 'no registrado'}"
    if plan.approvedAt:
        approval_line += f"    Fecha de aprobación: {_date(plan.approvedAt)}"
    pdf.cell(0, 6, approval_line, ln=True)
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 7, "Objetivo nutricional", ln=True)
    pdf.set_font("Helvetica", "", 10)
    goal_label = GOAL_LABELS.get(consultation.goal or "", consultation.goal or "-")
    pdf.cell(0, 6, f"Objetivo: {goal_label}", ln=True)
    pdf.cell(0, 6, f"Energia objetivo: {_num(consultation.targetCalories)} kcal", ln=True)
    pdf.cell(0, 6, f"Proteina: {_num(consultation.proteinGrams)} g   "
                   f"Carbohidratos: {_num(consultation.carbohydrateGrams)} g   "
                   f"Grasa: {_num(consultation.fatGrams)} g", ln=True)
    pdf.cell(0, 6, f"Fibra: {_num(consultation.fiberGrams)} g   "
                   f"Agua: {_num(consultation.waterLiters, 2)} L", ln=True)
    pdf.ln(4)

    if plan.summary:
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 7, "Resumen", ln=True)
        pdf.set_font("Helvetica", "", 10)
        _multi_cell(pdf, 5.5, _safe(plan.summary))
        pdf.ln(2)

    pdf.set_x(pdf.l_margin)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 7, "Comidas", ln=True)
    for meal in plan.meals:
        pdf.set_x(pdf.l_margin)
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_fill_color(240, 244, 248)
        pdf.cell(0, 7, f"{_safe(meal.mealType)} - {_safe(meal.name)}", ln=True, fill=True)
        pdf.set_font("Helvetica", "", 9.5)
        for food in meal.foods:
            line = f"- {_safe(food.foodName)}: {_quantity(food.quantity)} {_safe(food.unit) or ''}".rstrip()
            if food.calories is not None:
                line += f"  ({_num(food.calories)} kcal)"
            _multi_cell(pdf, 5, line, indent=4)
            if food.notes:
                pdf.set_font("Helvetica", "I", 8.5)
                pdf.set_text_color(90, 90, 90)
                _multi_cell(pdf, 4.5, _safe(food.notes), indent=8)
                pdf.set_text_color(0, 0, 0)
                pdf.set_font("Helvetica", "", 9.5)
        pdf.ln(1.5)
    pdf.ln(2)

    if plan.recommendations:
        pdf.set_x(pdf.l_margin)
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 7, "Recomendaciones", ln=True)
        pdf.set_font("Helvetica", "", 10)
        for recommendation in plan.recommendations:
            _multi_cell(pdf, 5.5, f"- {_safe(recommendation)}")
        pdf.ln(2)

    pdf.set_x(pdf.l_margin)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 7, "Fuentes documentales utilizadas", ln=True)
    pdf.set_font("Helvetica", "", 10)
    if sources:
        for source in sources:
            label = _safe(source.documentName)
            if source.institution:
                label += f" - {_safe(source.institution)}"
            _multi_cell(pdf, 5.5, f"- {label}")
    else:
        pdf.set_text_color(120, 120, 120)
        _multi_cell(pdf, 5.5, "No se recuperó contexto documental específico para este plan.")
        pdf.set_text_color(0, 0, 0)

    return bytes(pdf.output())

"""
Acceso a datos exclusivo del asistente IA contextual: búsquedas y consultas
agregadas que no existían en los repositorios de captura/planes, más la
trazabilidad de interacciones (sección 18).

Nunca ejecuta SQL crudo generado por el LLM (sección 9): todo aquí es
Prisma tipado, igual que el resto del proyecto.
"""
import json

PATIENT_INCLUDE = {"conditions": True}


async def search_patients_by_name(db, query: str, limit: int = 5) -> list:
    """Búsqueda insensible a mayúsculas por substring de nombre. `query` vacío
    no devuelve todos los pacientes (evita exponer el padrón completo)."""
    query = (query or "").strip()
    if not query:
        return []
    rows = await db.patient.find_many(include=PATIENT_INCLUDE, order={"createdAt": "desc"})
    needle = query.casefold()
    matches = [row for row in rows if needle in row.name.casefold()]
    return matches[:limit]


async def count_plans_by_status(db) -> list[dict]:
    rows = await db.dietplan.find_many()
    counts: dict[str, int] = {}
    for row in rows:
        counts[row.status] = counts.get(row.status, 0) + 1
    return [{"status": status, "count": count} for status, count in sorted(counts.items())]


async def list_patients_by_plan_status(db, status: str, limit: int = 20) -> list[dict]:
    plans = await db.dietplan.find_many(
        where={"status": status}, order={"createdAt": "desc"},
        include={"consultation": {"include": {"patient": True}}})
    results = []
    for plan in plans[:limit]:
        results.append({
            "patientId": plan.consultation.patient.id, "patientName": plan.consultation.patient.name,
            "planId": plan.id, "version": plan.version, "status": plan.status,
        })
    return results


async def log_interaction(db, *, prompt_version: str, model: str, user_question: str,
                           navigation_context: dict, tools_used: list[str], source_ids: list[str],
                           execution_time_ms: int, status: str, error_message: str | None = None) -> str:
    """Registra la interacción (sección 18). Nunca persiste la respuesta
    completa del LLM: solo metadatos de trazabilidad."""
    row = await db.assistantinteraction.create(data={
        "promptVersion": prompt_version, "model": model, "userQuestion": user_question[:1000],
        "navigationContext": json.dumps(navigation_context, ensure_ascii=False),
        "toolsUsed": json.dumps(tools_used, ensure_ascii=False),
        "sourceIds": json.dumps(source_ids, ensure_ascii=False),
        "executionTimeMs": execution_time_ms, "status": status,
        "errorMessage": (error_message or "")[:2000] or None,
    })
    return row.id

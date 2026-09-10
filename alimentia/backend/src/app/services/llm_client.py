"""
Cliente LLM (Fase 4).

`LLMClient.generate_structured` es la única abstracción que el resto del
dominio debe usar para hablar con el proveedor: no acopla nada a Ollama en
particular, solo requiere un endpoint compatible con la API de OpenAI. Las
funciones al final del archivo (`client`, `generate_diet_plan_draft`) son la
ruta heredada de `POST /api/v1/generate-draft`, anterior a Fase 1, y se
conservan sin cambios.
"""
import os
from typing import TypeVar

from openai import AsyncOpenAI
from pydantic import BaseModel

from app.schemas.patient import PatientIn

T = TypeVar("T", bound=BaseModel)

DEFAULT_TEMPERATURE = float(os.getenv("ALIMENTIA_LLM_TEMPERATURE", "0.2"))
# 240s por defecto: verificado empíricamente en Fase 4 con Ollama/llama3.2:3b en CPU
# (María González demo), donde una respuesta real tomó entre 110s y 235s. Un valor
# más bajo dispara el fallback sin response_format y puede apilar generaciones
# huérfanas en el proveedor (cada intento fallido deja la generación anterior corriendo
# del lado del servidor sin cancelarla).
DEFAULT_TIMEOUT_SECONDS = float(os.getenv("ALIMENTIA_LLM_TIMEOUT_SECONDS", "240"))


def llm_status() -> dict:
    """Estado configurado del proveedor LLM (Fase 6, sección 36).

    Nunca llama al proveedor para determinar el estado: solo reporta cómo
    está configurado este despliegue (base_url/modelo con sus valores por
    defecto), no si Ollama está realmente respondiendo en este momento.
    """
    return {
        "configured": True,
        "modelName": os.getenv("LLM_MODEL", "llama3.2:3b"),
    }


class LLMGenerationError(Exception):
    """El proveedor no respondió, o la respuesta no es JSON válido / no cumple el schema."""

    def __init__(self, message: str, raw_output: str | None = None):
        super().__init__(message)
        self.raw_output = raw_output


def _extract_json(raw: str) -> str:
    return raw.replace("```json", "").replace("```", "").strip()


class LLMClient:
    """Envoltorio genérico compatible con OpenAI/Ollama. No guarda API keys reales."""

    def __init__(self, base_url: str | None = None, model: str | None = None, timeout: float | None = None):
        self.base_url = base_url or os.getenv("LLM_API_URL", "http://ollama:11434/v1")
        self.model = model or os.getenv("LLM_MODEL", "gemma4")
        self.timeout = timeout if timeout is not None else DEFAULT_TIMEOUT_SECONDS
        self._client = AsyncOpenAI(base_url=self.base_url, api_key="EMPTY", timeout=self.timeout)

    @property
    def provider_name(self) -> str:
        return "ollama" if "ollama" in self.base_url else "openai-compatible"

    async def generate_structured(self, *, system_prompt: str, user_prompt: str,
                                   response_model: type[T], temperature: float = DEFAULT_TEMPERATURE) -> tuple[T, str]:
        """Llama al proveedor y valida la respuesta contra `response_model`.

        Devuelve (instancia validada, texto crudo del modelo). Lanza
        `LLMGenerationError` si el proveedor falla, la respuesta viene vacía,
        o el JSON no cumple la estructura esperada. Nunca lanza una excepción
        de red/parseo sin envolver.
        """
        messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]
        try:
            response = await self._client.chat.completions.create(
                model=self.model, messages=messages, temperature=temperature,
                response_format={"type": "json_object"},
            )
        except Exception:
            # No todos los backends OpenAI-compatibles soportan response_format; reintentamos sin él.
            try:
                response = await self._client.chat.completions.create(
                    model=self.model, messages=messages, temperature=temperature)
            except Exception as exc:
                raise LLMGenerationError(f"El proveedor LLM no respondió: {exc}") from exc

        raw = response.choices[0].message.content if response.choices else None
        if not raw or not raw.strip():
            raise LLMGenerationError("El proveedor LLM devolvió una respuesta vacía.")

        cleaned = _extract_json(raw)
        try:
            parsed = response_model.model_validate_json(cleaned)
        except Exception as exc:
            raise LLMGenerationError(
                f"La respuesta del modelo no cumple la estructura esperada: {exc}", raw_output=raw) from exc
        return parsed, raw


# --- Ruta heredada (pre-Fase 1), usada por POST /api/v1/generate-draft -----
# No se toca: firma y comportamiento idénticos a los del prototipo original.

client = AsyncOpenAI(
    base_url=os.getenv("LLM_API_URL", "http://ollama:11434/v1"),
    api_key="EMPTY"
)

MODEL_NAME = os.getenv("LLM_MODEL", "gemma4")


async def generate_diet_plan_draft(patient: PatientIn, nutritional_requirements: dict, exact_foods_context: list, clinical_guidelines: str) -> str:

    # Formateamos los datos del Excel para el modelo
    foods_text = "No database records requested."
    if exact_foods_context:
        foods_text = "\n".join([
            f"- {f['alimento']}: {f['kcal']} kcal, Proteínas: {f['proteina_g']}g, Grasas: {f['lipidos_g']}g, Carbohidratos: {f['carbohidratos_g']}g (por cada 100g)"
            for f in exact_foods_context
        ])

    system_prompt = (
        "You are 'AlimentIA', an AI assistant designed to help clinical nutritionists. "
        "Your task is to generate a first draft of a dietary plan based on the user's data.\n"
        "STRICT RULES:\n"
        "1. Never alter the provided deterministic TDEE calculations.\n"
        "2. You MUST design the menu using the exact nutritional values provided in the 'Verified Food Database'. Do not invent calories for those foods.\n"
        "3. Do not invent medical data. Tailor the food selection safely.\n"
        "4. Output ONLY valid, raw JSON. Do not include markdown code blocks (like ```json).\n"
        "5. The output MUST follow exactly this JSON TEMPLATE (fill the <TAGS> with the actual requested data, do not copy the tags themselves):\n"
        "6. CULINARY & CLINICAL SENSE: Create logical, appetizing meals. Do NOT fry foods. Add vegetables to make meals realistic. The total calories MUST be close to the Target TDEE. Follow these clinical guidelines from the Mexican Health Secretariat: {clinical_guidelines}\n"
        "7. CALORIC TARGET: You MUST provide large enough quantities (e.g., 250g, 300g) or enough food items to reach the Target TDEE. Do not leave the patient starving.\n"
        "8. LANGUAGE: You MUST write the 'time', 'food', 'instructions', and 'clinical_alerts' ENTIRELY IN SPANISH.\n"
        "{\n"
        "  \"meals\": [\n"
        "    {\n"
        "      \"time\": \"<e.g., Desayuno>\",\n"
        "      \"items\": [\n"
        "        {\"food\": \"<FOOD_NAME>\", \"quantity\": \"<QUANTITY>\", \"calories\": <KCAL>, \"protein\": \"<PROTEIN>g\", \"carbs\": \"<CARBS>g\"}\n"
        "      ],\n"
        "      \"instructions\": \"<PREPARATION>\"\n"
        "    }\n"
        "  ],\n"
        "  \"clinical_alerts\": [\"<MEDICAL_ALERT>\"]\n"
        "}"
    )

    user_prompt = (
        f"Patient Profile:\n"
        f"- Age: {patient.age}\n"
        f"- Gender: {patient.gender}\n"
        f"- Goal: {patient.goal}\n"
        f"- Pathologies: {', '.join(patient.pathologies) if patient.pathologies else 'None'}\n"
        f"- Allergies: {', '.join(patient.allergies_intolerances) if patient.allergies_intolerances else 'None'}\n"
        f"- Target Calories (TDEE): {nutritional_requirements['tdee_kcal']} kcal\n\n"
        f"Verified Food Database (Nutritional values per 100g):\n"
        f"{foods_text}\n\n"
        "Generate a one-day sample menu in JSON format fitting these parameters."
    )

    response = await client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.1
    )

    raw_content = response.choices[0].message.content
    cleaned_content = raw_content.replace(
        "```json", "").replace("```", "").strip()
    return cleaned_content

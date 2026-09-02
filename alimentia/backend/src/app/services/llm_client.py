import os
from openai import AsyncOpenAI
from app.schemas.patient import PatientIn

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

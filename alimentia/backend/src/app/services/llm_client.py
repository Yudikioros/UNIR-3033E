# src/app/services/llm_client.py
import os
from openai import AsyncOpenAI
from app.schemas.patient import PatientIn

# Fetch the URL from environment variables, defaulting to local vLLM port
VLLM_API_URL = os.getenv("VLLM_API_URL", "http://localhost:8000/v1")
# vLLM doesn't strictly need a real key, but the OpenAI client requires the parameter
VLLM_API_KEY = os.getenv("VLLM_API_KEY", "dummy-key")
MODEL_NAME = os.getenv("MODEL_NAME", "Qwen/Qwen2.5-7B-Instruct-AWQ")

client = AsyncOpenAI(
    base_url=VLLM_API_URL,
    api_key=VLLM_API_KEY
)


async def generate_diet_plan_draft(patient: PatientIn, nutritional_requirements: dict) -> str:
    
    # Añadimos un esquema JSON estricto al prompt
    system_prompt = (
        "You are 'AlimentIA', an AI assistant designed to help clinical nutritionists. "
        "Your task is to generate a first draft of a dietary plan based on the user's data. "
        "You MUST strictly follow these rules:\n"
        "1. Never alter the provided deterministic TDEE calculations.\n"
        "2. Do not invent medical data. Tailor the food selection safely.\n"
        "3. Output ONLY valid, raw JSON. Do not include markdown code blocks (like ```json), introductions, or conclusions.\n"
        "4. You MUST use exactly this JSON structure:\n"
        "{\n"
        "  \"meals\": [\n"
        "    {\n"
        "      \"time\": \"Desayuno\",\n"
        "      \"items\": [\n"
        "        {\"food\": \"Avena\", \"quantity\": \"1/2 taza\", \"calories\": 150}\n"
        "      ],\n"
        "      \"instructions\": \"Preparar con agua y canela.\"\n"
        "    }\n"
        "  ],\n"
        "  \"clinical_alerts\": [\"El paciente tiene resistencia a la insulina, moderar carbohidratos simples.\"]\n"
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
        "Generate a one-day sample menu in JSON format fitting these parameters."
    )

    response = await client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.1 # Bajamos aún más la temperatura para evitar creatividad en la sintaxis
    )
    
    raw_content = response.choices[0].message.content
    cleaned_content = raw_content.replace("```json", "").replace("```", "").strip()
    return cleaned_content

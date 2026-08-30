import json
from fastapi import FastAPI, HTTPException
from app.schemas.patient import PatientIn
from app.services.calculator import get_nutritional_baseline
from app.services.llm_client import generate_diet_plan_draft

app = FastAPI(title="AlimentIA Backend")

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "AlimentIA Backend"}

@app.post("/api/v1/generate-draft")
async def generate_draft(patient: PatientIn):
    try:
        # 1. Calculate deterministic formulas
        nutritional_requirements = get_nutritional_baseline(
            weight=patient.weight,
            height=patient.height,
            age=patient.age,
            gender=patient.gender,
            activity_level=patient.activity_level
        )
        
        # TODO: 2. Query Knowledge Base (RAG) for pathologies/interactions
        
        # 3. Send prompt to vLLM
        llm_response_string = await generate_diet_plan_draft(patient, nutritional_requirements)
        
        try:
            # Parse the JSON string
            diet_plan_json = json.loads(llm_response_string)
        except json.JSONDecodeError as e:
            # Si falla, devolvemos el error pero TAMBIÉN el texto crudo para poder debuggear
            return {
                "message": f"Error parsing JSON from LLM: {str(e)}",
                "raw_llm_output": llm_response_string
            }
        
        return {
            "message": "Draft generated successfully.",
            "calculated_requirements": nutritional_requirements,
            "diet_plan": diet_plan_json
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
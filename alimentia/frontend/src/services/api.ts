export interface PatientData {
  age: number;
  gender: string;
  weight: number;
  height: number;
  goal: string;
  activity_level: string;
  pathologies: string[];
  medications: string[];
  allergies_intolerances: string[];
  food_preferences: string[];
  cultural_restrictions: string[];
  budget: string;
  regional_availability: string;
}

export async function generateDietDraft(patientData: PatientData) {
  // Escribimos la URL directamente aquí para ignorar variables cacheadas
  const response = await fetch("http://localhost:8080/api/v1/generate-draft", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(patientData),
  });

  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || `Error del servidor: ${response.statusText}`);
  }

  return response.json();
}

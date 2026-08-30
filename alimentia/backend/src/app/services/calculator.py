# src/app/services/calculator.py

def calculate_bmr(weight_kg: float, height_m: float, age_yrs: int, gender: str) -> float:
    """
    Calculates the Basal Metabolic Rate (BMR) using the Mifflin-St Jeor equation.
    Note: The formula requires height in centimeters.
    """
    height_cm = height_m * 100.0
    
    # Base formula calculation
    base_bmr = (10.0 * weight_kg) + (6.25 * height_cm) - (5.0 * age_yrs)
    
    gender_normalized = gender.strip().lower()
    
    if gender_normalized == "male":
        return base_bmr + 5.0
    elif gender_normalized == "female":
        return base_bmr - 161.0
    else:
        raise ValueError("Gender must be 'male' or 'female'")

def calculate_tdee(bmr: float, activity_level: str) -> float:
    """
    Calculates Total Daily Energy Expenditure (TDEE) based on activity multipliers.
    """
    multipliers = {
        "sedentary": 1.2,
        "light": 1.375,
        "moderate": 1.55,
        "active": 1.725,
        "very active": 1.9
    }
    
    activity_normalized = activity_level.strip().lower()
    
    if activity_normalized not in multipliers:
        # Default to sedentary if input is unrecognized to err on the side of caution
        return bmr * 1.2
        
    return bmr * multipliers[activity_normalized]

def get_nutritional_baseline(weight: float, height: float, age: int, gender: str, activity_level: str) -> dict:
    """
    Orchestrates the calculations and returns a dictionary with the energy requirements.
    """
    bmr = calculate_bmr(weight, height, age, gender)
    tdee = calculate_tdee(bmr, activity_level)
    
    return {
        "bmr_kcal": round(bmr, 2),
        "tdee_kcal": round(tdee, 2)
    }

import re
from api import get_data


COMPOUND_PATTERN = (
    r"\b(?:"
    r"press|pull|squat|row|ups|up|bench|incline|"
    r"push|front|squats|plank|calf|biceps|deadlift|"
    r"kettlebell|down|sit|hold|trx|wide|dips|"
    r"wall|knee|lunges|floor|split|bridge|clean|"
    r"thrust|rowing|narrow|smith"
    r")\b"
)

ISOLATED_PATTERN = (
    r"\b(?:"
    r"curls|extension|triceps|lateral|fly|dumbbells|"
    r"overhead|tricep|pushdown|preacher|external"
    r")\b"
)


def classify_effort(exercise: dict) -> str:
    category = (exercise.get("category") or {}).get("name", "").lower()
    
    translations = exercise.get("translations") or []
    
    name = ""
    for t in translations:
        if t.get("language") == 2:
            name = t.get("name") or ""
            break

    total_muscles = (
        len(exercise.get("muscles") or []) +
        len(exercise.get("muscles_secondary") or [])
    )

    if category == "cardio":
        return "cardio"

    if not name or total_muscles == 0:
        return "other"

    if total_muscles == 1:
        tendencia = "isolated"
    else:
        tendencia = "compound"

    if tendencia == "isolated" and re.search(ISOLATED_PATTERN, name, re.IGNORECASE):
        return "isolated"

    if tendencia == "compound" and re.search(COMPOUND_PATTERN, name, re.IGNORECASE):
        return "compound"

    return "other"


def get_exercise_type(exercise_id: int) -> str:
    exercise = get_data(f"exerciseinfo/{exercise_id}/")
    return classify_effort(exercise)
import json
import re
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path

from . import api

WORKOUTS_DIR = Path(__file__).resolve().parent.parent / "workouts"


# ===========================================================================
# [BASE LOCAL] VALIDAÇÃO, FICHEIROS E SELEÇÃO
# ===========================================================================

def exercise_name(exercise):
    """Nome em português (7), com inglês como alternativa."""
    for language in (7, 2):
        for translation in exercise.get("translations") or []:
            if translation.get("language") == language and translation.get("name"):
                return translation["name"]
    return ""


def validate_workout(workout):
    try:
        if type(workout["version"]) is not int or workout["version"] != 1 or not isinstance(workout["name"], str):
            raise ValueError
        if not 1 <= len(workout["name"].strip()) <= 25:
            raise ValueError
        if not isinstance(workout["sessions"], list) or not 1 <= len(workout["sessions"]) <= 7:
            raise ValueError
        for session in workout["sessions"]:
            if not isinstance(session["name"], str) or not 1 <= len(session["name"].strip()) <= 20:
                raise ValueError
            if not isinstance(session["muscles"], list) or not isinstance(session["exercises"], list):
                raise ValueError
            if not session["exercises"]:
                raise ValueError
            for name in session["muscles"]:
                if not isinstance(name, str):
                    raise ValueError
            for entry in session["exercises"]:
                if (type(entry["id"]) is not int or entry["id"] <= 0
                        or not isinstance(entry["name"], str) or not entry["name"].strip()):
                    raise ValueError
                if type(entry["sets"]) is not int or not 1 <= entry["sets"] <= 50:
                    raise ValueError
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("Workout inválido: verifique nomes, sessões, músculos, exercícios e séries (1–50).") from error
    return workout


def save_workout(workout):
    validate_workout(workout)
    WORKOUTS_DIR.mkdir(exist_ok=True)
    name = re.sub(r"[^\w-]+", "_", workout["name"]).strip("_") or "treino"
    path = WORKOUTS_DIR / f"{name}.json"
    counter = 2
    while path.exists():
        path = WORKOUTS_DIR / f"{name}_{counter}.json"
        counter += 1
    with path.open("x", encoding="utf-8") as file:
        json.dump(workout, file, ensure_ascii=False, indent=2)
    print(f"Treino guardado: {path.name}")
    return path


def load_workout(filename):
    path = WORKOUTS_DIR / filename
    if Path(filename).name != filename or path.suffix != ".json" or path.resolve().parent != WORKOUTS_DIR.resolve():
        raise ValueError("Escolha um ficheiro JSON dentro de workouts/.")
    with path.open(encoding="utf-8") as file:
        return validate_workout(json.load(file))


def filtered_exercises(equipment, muscles):
    available = []
    targets = []
    for item in equipment:
        available.append(item["id"])
    for item in muscles:
        targets.append(item["id"])
    found = []
    for raw in api.get_list("exerciseinfo/", {"muscles": targets, "limit": 100}):
        allowed = True
        for item in raw.get("equipment", []):
            if item["id"] not in available:
                allowed = False
        name = exercise_name(raw)
        if allowed and name:
            found.append({"id": raw["id"], "name": name})
    return found

# ===========================================================================
# [PARTILHADO WGER] LEITURA DA ESTRUTURA E PERÍODOS
# ===========================================================================

def read_structure(ident, token):
    structure = api.request("GET", f"routine/{ident}/structure/", token)
    workout = {"version": 1, "id": ident, "name": structure["name"], "sessions": []}
    for day in structure["days"]:
        if day["is_rest"]:
            continue
        session = {"id": day["id"], "name": day["name"], "muscles": [], "exercises": []}
        for slot in day["slots"]:
            for entry in slot["entries"]:
                configs = entry.get("set_nr_configs", [])
                if (len(configs) != 1 or entry.get("max_set_nr_configs") or entry.get("config")
                        or entry.get("type", "normal") != "normal" or day.get("type", "custom") != "custom"):
                    raise ValueError("O TCLI aceita apenas workouts simples com séries fixas.")
                config = configs[0]
                try:
                    value = Decimal(str(config["value"]))
                except InvalidOperation as error:
                    raise ValueError("Número de séries inválido.") from error
                if (not value.is_finite() or value != int(value) or config["iteration"] != 1
                        or config.get("operation", "r") != "r" or config.get("requirements")):
                    raise ValueError("Configuração de séries não suportada.")
                raw = api.get_data(f"exerciseinfo/{entry['exercise']}/")
                name = exercise_name(raw)
                if not name:
                    raise ValueError("Exercício sem nome em português ou inglês; template não compatível.")
                session["exercises"].append({"id": entry["exercise"], "name": name,
                                             "slot_entry": entry["id"], "sets": int(value)})
                for muscle in (raw.get("muscles") or []) + (raw.get("muscles_secondary") or []):
                    name = muscle.get("name_en") or muscle.get("name")
                    if name not in session["muscles"]:
                        session["muscles"].append(name)
        workout["sessions"].append(session)
    return validate_workout(workout)


def current_period(weekly=False):
    monday = date.today() - timedelta(days=date.today().weekday())
    return {"start": monday.isoformat(), "end": (monday + timedelta(days=83 if weekly else 6)).isoformat()}

# ===========================================================================
# [EXPORTACAO WGER] CRIAR TEMPLATE
# Também usado pela ativação, que cria uma cópia antes de substituir a rotina.
# ===========================================================================

def create_template(workout, token):
    validate_workout(workout)
    data = {**current_period(), "name": workout["name"], "is_template": True,
            "is_public": False, "fit_in_week": True}
    routine = api.request("POST", "routine/", token, data)
    try:
        for order, session in enumerate(workout["sessions"]):
            day = api.request("POST", "day/", token,
                              {"routine": routine["id"], "name": session["name"], "order": order})
            for position, entry in enumerate(session["exercises"]):
                slot = api.request("POST", "slot/", token, {"day": day["id"], "order": position})
                saved = api.request("POST", "slot-entry/", token,
                                    {"slot": slot["id"], "exercise": entry["id"],
                                     "repetition_unit": 1, "weight_unit": 1})
                api.request("POST", "sets-config/", token,
                            {"slot_entry": saved["id"], "iteration": 1, "value": entry["sets"], "operation": "r"})
    except (RuntimeError, KeyboardInterrupt, EOFError) as error:
        raise RuntimeError(f"Template #{routine['id']} incompleto. "
                           "Não repetir a exportação automaticamente.") from error
    return routine

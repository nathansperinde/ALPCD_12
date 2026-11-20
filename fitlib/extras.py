import re
from typing import Any

from . import api
from .exercises import LANGUAGE, _format, _name_in_english, classify_effort, clean_description


# [X1] FIND
# Pesquisa textual de exercícios

def word_pattern(word: str) -> re.Pattern:
    word = word.lower()

    # Plurais irregulares
    exceptions = {
        "calf": "calves",
        "foot": "feet",
        "scapula": "scapulae",
        "vertebra": "vertebrae"
    }

    for singular, plural in exceptions.items():
        if word in (singular, plural):
            pattern = rf"(?:{singular}|{plural})"
            return re.compile(rf"\b{pattern}\b", re.IGNORECASE)

    # fly / flies, body / bodies
    if re.search(r"[^aeiou](?:y|ies)$", word):
        base = re.sub(r"(?:y|ies)$", "", word)
        pattern = rf"{re.escape(base)}(?:y|ies)"

    # press / presses, bench / benches
    elif re.search(r"(?:ss|sh|ch|x|z)(?:es)?$", word):
        base = re.sub(r"es$", "", word)
        pattern = rf"{re.escape(base)}(?:es)?"

    # curl / curls, dumbbell / dumbbells
    else:
        base = re.sub(r"s$", "", word) if not word.endswith(("ss", "us", "is")) else word
        pattern = rf"{re.escape(base)}s?"

    return re.compile(rf"\b{pattern}\b", re.IGNORECASE)


def find_exercises(query: str, limit: int = 20, deep: bool = False, show_description: bool = False, raw: bool = False) -> list[dict]:

    if limit <= 0:
        raise ValueError("O limite deve ser positivo.")

    words = re.findall(r"[^\W_]+", query)

    if not words:
        raise ValueError("Pesquisa vazia.")

    params = {"language__code": "en", "limit": 100}

    if not deep:
        params["name__search"] = query.strip()

    patterns = [
        word_pattern(word)
        for word in set(words)
    ] if deep else []

    def filter_exercise(exercise: dict) -> dict | None:
        data = _format(exercise)

        if data is None:
            return None

        description = ""

        if deep or show_description:
            description = clean_description(data["description"])

        if deep:
            text = data["name"] + " " + description

            if not all(pattern.search(text) for pattern in patterns):
                return None

        if raw:
            return exercise

        result = {"id": data["id"], "name": data["name"]}

        if show_description:
            result["description"] = description

        return result

    return api.get_list(
        "exerciseinfo/",
        params=params,
        max_items=limit,
        transform=filter_exercise
    )


# [X2] COMPARE
# Comparação de exercícios

def _compare_attribute(items: list[dict], field: str) -> dict:
    occurrences = {}

    for item in items:
        values = item[field]

        if not isinstance(values, list):
            values = [values]

        for value in set(values) - {None, ""}:
            occurrences.setdefault(value, []).append(item["id"])

    common = []
    shared = {}
    exclusive = {}

    for value, found in sorted(occurrences.items()):
        if len(found) == len(items):
            common.append(value)

        elif len(found) > 1:
            shared[value] = found

        else:
            exclusive[value] = found[0]

    result = {"comuns_a_todos": common}

    if len(items) > 2:
        result["partilhados"] = shared

    result["exclusivos"] = exclusive

    return result


def compare_exercises(ids: list[int]) -> dict:
    if len(ids) < 2:
        raise ValueError("Indique pelo menos dois exercícios.")

    if len(ids) != len(set(ids)) or min(ids) <= 0:
        raise ValueError("Os IDs devem ser positivos e diferentes.")

    items = []

    for exercise_id in ids:
        exercise = api.get_data(f"exerciseinfo/{exercise_id}/")
        data = _format(exercise)

        if data is None:
            raise ValueError(f"Exercício {exercise_id} sem tradução inglesa.")

        data["type"] = classify_effort(exercise)

        items.append(data)

    comparison = {}

    for field in ("category", "type", "muscles", "muscles_secondary", "equipment"):
        comparison[field] = _compare_attribute(items, field)

    return {"total_exercicios": len(items), "comparacao": comparison}


# [SUPORTE C] TYPE
# Pesquisa textual por tipo de esforço

def search_exercise_types(query: str, limit: int = 20, deep: bool = False) -> list[dict]:
    found = find_exercises(query, limit, deep, raw=True)
    return [
        {
            "id": exercise["id"],
            "name": _name_in_english(exercise),
            "type": classify_effort(exercise)
        }
        for exercise in found
    ]


# [X3] DIFFICULTY
# Estimativa de dificuldade

# Palavras do nome que sugerem um exercício mais difícil
ADVANCED_PATTERN = re.compile(
    r"\b(?:single[- ]?(?:leg|arm)|one[- ]?(?:leg|arm)|pistol|deficit|weighted|"
    r"snatch|clean|jerk|muscle[- ]?up|handstand|archer|plyo\w*|explosive)\b",
    re.IGNORECASE,
)
# Palavras que sugerem um exercício guiado/apoiado, mais fácil de executar
BEGINNER_PATTERN = re.compile(
    r"\b(?:assisted|machine|seated|supported|wall|kneeling|stretch\w*)\b",
    re.IGNORECASE,
)
# Pesos livres difíceis de controlar
HARD_EQUIPMENT = {"barbell", "kettlebell"}


def _unique_matches(pattern: re.Pattern, text: str) -> list[str]:
    """Todas as correspondências de `pattern` em `text`, sem repetidos, por ordem."""
    found: list[str] = []
    for match in pattern.finditer(text):
        word = match.group(0).lower()
        if word not in found:
            found.append(word)
    return found


def score_difficulty(name: str, n_muscles: int, equipment: list[str]) -> tuple[int, list[str]]:
    """Calcular a pontuação de dificuldade e as razões (cada razão mostra os pontos)."""
    score = 0
    reasons: list[str] = []

    if n_muscles >= 4:
        points = 2
    elif n_muscles >= 2:
        points = 1
    else:
        points = 0
    if points:
        score += points
        reasons.append(f"{n_muscles} músculos envolvidos (+{points})")

    advanced = _unique_matches(ADVANCED_PATTERN, name)
    if advanced:
        score += 2
        reasons.append(f"palavras avançadas no nome: {', '.join(advanced)} (+2)")

    beginner = _unique_matches(BEGINNER_PATTERN, name)
    if beginner:
        score -= 1
        reasons.append(f"palavras de apoio no nome: {', '.join(beginner)} (-1)")

    hard = [e for e in equipment if e and e.lower() in HARD_EQUIPMENT]
    if hard:
        score += 1
        reasons.append(f"equipamento exigente: {', '.join(hard)} (+1)")

    return score, reasons


def level_from_score(score: int) -> str:
    if score <= 1:
        return "iniciante"
    if score <= 3:
        return "intermédio"
    return "avançado"


def exercise_difficulty(exercise_id: int, refresh: bool = False) -> dict[str, Any]:
    """Estimar a dificuldade do exercício com o ID dado (pede exerciseinfo/<id>/)."""
    if exercise_id <= 0:
        raise ValueError("O ID do exercício deve ser positivo.")

    exercise = api.get_data(f"exerciseinfo/{exercise_id}/", refresh=refresh)
    
    name = _name_in_english(exercise)
    if name is None:
        raise ValueError(f"Exercício {exercise_id} sem tradução inglesa.")

    n_muscles = len(exercise.get("muscles") or []) + len(exercise.get("muscles_secondary") or [])
    equipment = [e.get("name") for e in exercise.get("equipment") or []]

    score, reasons = score_difficulty(name, n_muscles, equipment)
    return {
        "id": exercise_id,
        "name": name,
        "level": level_from_score(score),
        "score": score,
        "reasons": reasons,
    }


# [X4] INGREDIENT
# Consulta de valores nutricionais

PAGE_SIZE = 50  # pedimos uma só página; chega para filtrar e mostrar poucos resultados


def _number(value: Any) -> float | None:
    """A API devolve os nutrientes como texto ("165.0") ou null: converter com segurança."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _scaled(value: Any, grams: float) -> float | None:
    number = _number(value)
    return None if number is None else round(number * grams / 100, 1)


def ingredient_info(name: str, limit: int = 5, grams: float = 100.0,
                    refresh: bool = False) -> list[dict[str, Any]]:
    """Pesquisar ingredientes pelo nome e devolver calorias e macronutrientes."""
    words = re.findall(r"\w+", name)
    if not words:
        raise ValueError("Indique o nome de um ingrediente.")
    if grams <= 0:
        raise ValueError("A quantidade em gramas deve ser positiva.")
    if limit <= 0:
        raise ValueError("O limite deve ser positivo.")

    params = {"name__search": name.strip(), "language": LANGUAGE, "limit": PAGE_SIZE}
    page = api.get_data("ingredientinfo/", params, refresh=refresh)
    items = page.get("results")
    if not isinstance(items, list):
        raise RuntimeError("A API não devolveu uma lista de ingredientes.")

    # Guarda: a API pode ignorar um filtro em silêncio e devolver o catálogo todo.
    # Só ficamos com ingredientes cujo nome contém TODAS as palavras pedidas.
    patterns = [re.compile(r"\b" + re.escape(word), re.IGNORECASE) for word in words]
    matches = [
        item for item in items
        if isinstance(item, dict)
        and all(pattern.search(item.get("name") or "") for pattern in patterns)
    ]
    if not matches:
        raise RuntimeError(f"Nenhum ingrediente encontrado para '{name.strip()}'.")

    return [
        {
            "name": item["name"],
            "quantity_g": grams,
            "energy_kcal": _scaled(item.get("energy"), grams),
            "protein_g": _scaled(item.get("protein"), grams),
            "carbs_g": _scaled(item.get("carbohydrates"), grams),
            "fat_g": _scaled(item.get("fat"), grams),
        }
        for item in matches[:limit]
    ]

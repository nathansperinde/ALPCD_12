"""Alíneas A/B integradas de Rafael; pontos de implementação de c) e d)."""

import re
from typing import Any

from . import api, processing

LANGUAGE = 2


# Lógica de Rafael em AeB/fitcli.py, adaptada aos módulos principais.
def _name_in_english(exercise: dict) -> str | None:
    for translation in exercise.get("translations", []):
        if translation.get("language") == LANGUAGE and translation.get("name"):
            return translation["name"]
    return None


def _format(exercise: dict) -> dict[str, Any] | None:
    """Normalizar sem perder os dados úteis às próximas alíneas."""
    name = _name_in_english(exercise)
    if name is None:
        return None
    translation = next(
        item for item in exercise["translations"]
        if item.get("language") == LANGUAGE and item.get("name") == name
    )
    return {
        "id": exercise["id"],
        "name": name,
        "category": (exercise.get("category") or {}).get("name"),
        "equipment": [item.get("name") for item in exercise.get("equipment", [])],
        "muscles": [
            item.get("name_en") or item.get("name")
            for item in exercise.get("muscles", [])
        ],
        "muscles_secondary": [
            item.get("name_en") or item.get("name")
            for item in exercise.get("muscles_secondary", [])
        ],
        "description": translation.get("description") or "",
    }


def top_exercises(limit: int, refresh: bool = False) -> list[dict[str, Any]]:
    """a) Obter até N exercícios recentes com tradução inglesa."""
    if limit <= 0:
        raise ValueError("O limite deve ser positivo.")
    params = {"language": LANGUAGE, "ordering": "-created", "limit": min(limit, 100)}
    # get_list/get_data de Nathan aceitam o endpoint relativo e os next absolutos.
    return api.get_list(
        "exerciseinfo/", params, max_items=limit,
        refresh=refresh, transform=_format,
    )


def _matching_ids(items: list[dict], pattern: re.Pattern) -> list[int]:
    return [
        item["id"] for item in items
        if pattern.search(item.get("name_en") or "")
        or pattern.search(item.get("name") or "")
    ]


def search_exercises(target: str, limit: int, refresh: bool = False) -> list[dict[str, Any]]:
    """b) Pesquisar por músculo/categoria, sem repetir IDs entre filtros."""
    target = target.strip()
    if not target:
        raise ValueError("Indique um músculo ou uma categoria não vazios.")
    if limit <= 0:
        raise ValueError("O limite deve ser positivo.")
    pattern = re.compile(re.escape(target), re.IGNORECASE)
    muscles = api.get_list("muscle/", {"limit": 100}, refresh=refresh)
    categories = api.get_list("exercisecategory/", {"limit": 100}, refresh=refresh)

    # A wger recebe IDs nos filtros; resolver o nome introduzido nos catálogos.
    filters = [("muscles", ident) for ident in _matching_ids(muscles, pattern)]
    filters += [("category", ident) for ident in _matching_ids(categories, pattern)]
    if not filters:
        raise RuntimeError(f"'{target}' não corresponde a nenhum músculo nem categoria.")

    seen: set[int] = set()

    def unique(exercise: dict) -> dict[str, Any] | None:
        # O mesmo ID pode aparecer em vários filtros/páginas; nomes podem coincidir.
        if exercise["id"] in seen:
            return None
        formatted = _format(exercise)
        if formatted is not None:
            seen.add(exercise["id"])
        return formatted

    results: list[dict[str, Any]] = []
    # Unir correspondências de músculos OU categorias, com um limite global.
    for field, ident in filters:
        if len(results) >= limit:
            break
        params = {"language": LANGUAGE, field: ident, "limit": min(limit, 100)}
        results += api.get_list(
            "exerciseinfo/", params, max_items=limit - len(results),
            refresh=refresh, transform=unique,
        )
    return results


# Algoritmo para o tipo de exercício e funções extras - Nathan

# EXTRA: função para pesquisar pelo exercício através do nome ou do nome e descrição
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
            description = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", data["description"])).strip()

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

# Função para classificar o tipo do exercício
COMPOUND_PATTERN = (
    r"\b(?:"
    r"press|pull|squat|row|ups|up|bench|incline|"
    r"push|front|squats|plank|biceps|calf|deadlift|"
    r"kettlebell|down|sit|hold|trx|wide|dips|split|"
    r"wall|knee|lunges|floor|thrust|rowing|smith|"
    r"bridge|clean|narrow"
    r")\b"
)

ISOLATED_PATTERN = (
    r"\b(?:"
    r"curls|extension|triceps|lateral|fly|dumbbells|"
    r"overhead|tricep|preacher|pushdown|kickback"
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

# EXTRA: função para comparar exercícios
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


def exercise_type(exercise_id: int) -> str:
    """c): inferir o esforço pela descrição, categoria e músculos."""
    exercise = api.get_data(f"exerciseinfo/{exercise_id}/")
    return classify_effort(exercise)


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


def equipment_frequency(category: str) -> list[dict[str, Any]]:
    """TODO d): extrair equipamento com re e ordenar por frequência."""
    raise NotImplementedError("Comando equipment ainda por implementar.")

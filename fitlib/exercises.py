import csv
import json
import re
from pathlib import Path
from typing import Any

from . import api


# ===========================================================================
# [BASE] IDIOMA E NORMALIZAÇÃO
# Representação de exercício partilhada pelas alíneas e pelos extras.
# ===========================================================================

LANGUAGE = 2


def _name_in_english(exercise: dict) -> str | None:
    for translation in exercise.get("translations", []):
        if translation.get("language") == LANGUAGE and translation.get("name"):
            return translation["name"]
    return None


def _format(exercise: dict) -> dict[str, Any] | None:
    """Normalizar os dados dos exercícios com tradução inglesa."""
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


# ===========================================================================
# [A/B] CONSULTA E PESQUISA POR MÚSCULO/CATEGORIA
# ===========================================================================

def top_exercises(limit: int, refresh: bool = False) -> list[dict[str, Any]]:
    """a) Obter até N exercícios recentes com tradução inglesa."""
    if limit <= 0:
        raise ValueError("O limite deve ser positivo.")
    params = {"language": LANGUAGE, "ordering": "-created", "limit": min(limit, 100)}
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


# ===========================================================================
# [C] CLASSIFICAÇÃO DO ESFORÇO
# Preservar as regras existentes: são reutilizadas pelo plano da alínea e).
# ===========================================================================

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


def exercise_type(exercise_id: int) -> str:
    """c) Classificar o esforço pela categoria, nome e músculos."""
    exercise = api.get_data(f"exerciseinfo/{exercise_id}/")
    return classify_effort(exercise)


# ===========================================================================
# [D] FREQUÊNCIA DE EQUIPAMENTO
# ===========================================================================

def equipment_frequency(
    category: str
) -> list[dict[str, int]]:
    """d) Contar as menções a equipamentos nas descrições de uma categoria."""
    categories = api.get_list(
        "exercisecategory/"
    )

    pattern = re.compile(
        rf"^{re.escape(category.strip())}$",
        re.IGNORECASE
    )

    category_ids = _matching_ids(
        categories,
        pattern
    )

    if not category_ids:
        raise ValueError(
            f"Categoria não encontrada: {category}"
        )

    category_id = category_ids[0]

    exercises = api.get_list(
        "exerciseinfo/",
        params={"category": category_id},
        transform=_format
    )

    descriptions = []

    for exercise in exercises:
        descriptions.append(exercise["description"])

    return count_equipment(
        descriptions
    )

# PROCESSAMENTO DE DESCRIÇÕES

EQUIPMENT_PATTERNS = {
    "Barbell": re.compile(
        r"\bbarbells?\b",
        re.IGNORECASE
    ),
    # Não reconhecer "bench" dentro de "incline bench".
    "Bench": re.compile(
        r"(?<!incline )\bbench(?:es)?\b",
        re.IGNORECASE
    ),
    "Cable machine": re.compile(
        r"\b(?:cable\s+machines?|cables?)\b",
        re.IGNORECASE
    ),
    "Dumbbell": re.compile(
        r"\bdumbbells?\b",
        re.IGNORECASE
    ),
    "Gym mat": re.compile(
        r"\b(?:gym|exercise)\s+mats?\b",
        re.IGNORECASE
    ),
    "Incline bench": re.compile(
        r"\bincline\s+bench(?:es)?\b",
        re.IGNORECASE
    ),
    "Kettlebell": re.compile(
        r"\bkettlebells?\b",
        re.IGNORECASE
    ),
    "Pull-up bar": re.compile(
        r"\bpull[- ]up\s+bars?\b",
        re.IGNORECASE
    ),
    "Resistance band": re.compile(
        r"\bresistance\s+bands?\b",
        re.IGNORECASE
    ),
    "SZ-Bar": re.compile(
        r"\b(?:sz|ez)[- ]bar\b",
        re.IGNORECASE
    ),
    "Swiss Ball": re.compile(
        r"\b(?:swiss|stability)\s+balls?\b",
        re.IGNORECASE
    ),
    "none (bodyweight exercise)": re.compile(
        r"\b(?:bodyweight|body\s+weight)\b",
        re.IGNORECASE
    )
}


HTML_TAGS = re.compile(r"<[^>]+>")


def clean_description(description: str) -> str:
    """Remover tags HTML e normalizar os espaços da descrição."""
    cleaned = HTML_TAGS.sub(" ", description)
    cleaned = " ".join(cleaned.split())
    return cleaned


def count_equipment(
    descriptions: list[str],
    limpar_html: bool = True
) -> list[dict[str, int]]:
    """Contar as menções a cada equipamento nas descrições."""
    contagem = {}

    for description in descriptions:
        texto = description

        # Limpar HTML para não contar equipamento nos atributos das tags.
        if limpar_html:
            texto = clean_description(description)

        for equipment, pattern in EQUIPMENT_PATTERNS.items():
            encontrados = pattern.findall(texto)
            quantidade = len(encontrados)

            if quantidade > 0:
                anterior = contagem.get(equipment, 0)
                contagem[equipment] = anterior + quantidade

    resultado = []

    for equipment, quantidade in contagem.items():
        resultado.append({
            equipment.lower(): quantidade
        })

    # A ordenação por frequência decrescente fica por implementar.
    return resultado

# ===========================================================================
# [E] PLANO POR ALVO E ESFORÇO
# ===========================================================================

def search_by_category(muscle: str, category: str, n: int) -> list[dict[str, Any]]:
    """Pesquisar mais candidatos até reunir N exercícios do esforço pedido."""
    if n <= 0:
        raise ValueError("O limite deve ser positivo.")
    if category not in ("compound", "isolated", "any"):
        raise ValueError("Indique compound, isolated ou any.")

    resultado = []
    verificados = {}
    limite_pesquisa = n

    while True:
        candidatos = search_exercises(muscle, limite_pesquisa)

        for exercise in candidatos:
            exercise_id = exercise["id"]
            if exercise_id in verificados:
                continue

            tipo = exercise_type(exercise_id)
            verificados[exercise_id] = tipo

            if category == "any" or tipo == category:
                exercise = exercise.copy()
                exercise["type"] = tipo
                resultado.append(exercise)

                if len(resultado) == n:
                    return resultado

        if len(candidatos) < limite_pesquisa:
            return resultado

        limite_pesquisa += n


def build_workout(targets: str, effort: str, limit: int) -> dict[str, list[dict[str, Any]]]:
    """e) Reutilizar pesquisa e classificação, com um limite por alvo."""
    if limit <= 0:
        raise ValueError("O limite deve ser positivo.")
    if effort not in ("compound", "isolated", "any"):
        raise ValueError("Indique compound, isolated ou any.")

    alvos = []
    for target in targets.split(","):
        target = target.strip()
        if not target:
            raise ValueError("Indique alvos não vazios separados por vírgula.")
        alvos.append(target)

    plano = {}
    for target in alvos:
        if target not in plano:
            plano[target] = search_by_category(target, effort, limit)

    return plano

# ===========================================================================
# [SAÍDA BASE] JSON
# ===========================================================================

def print_json(data: Any) -> None:
    """Imprimir JSON indentado, preservando acentos e terminando com newline."""
    print(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False))

# ===========================================================================
# [EXPORTACAO CSV] PLANO DA ALÍNEA E
# ===========================================================================

CSV_FIELDS = ("target", "id", "name", "category", "equipment", "type")


def _csv_value(value: Any) -> Any:
    """Representar estruturas numa célula sem perder os seus campos."""
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, allow_nan=False)
    return value


def write_workout_csv(workout: dict[str, list[dict[str, Any]]], path: Path) -> None:

    with Path(path).open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for target, exercises in workout.items():
            for exercise in exercises:
                row = {
                    field: _csv_value(exercise.get(field, ""))
                    for field in CSV_FIELDS if field != "target"
                }
                writer.writerow({"target": target, **row})

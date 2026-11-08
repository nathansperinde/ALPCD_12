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


def exercise_type(exercise_id: int) -> str:
    """TODO c): inferir o esforço pela descrição, categoria e músculos."""
    raise NotImplementedError("Comando type ainda por implementar.")


def equipment_frequency(category: str) -> list[dict[str, Any]]:
    """TODO d): extrair equipamento com re e ordenar por frequência."""
    raise NotImplementedError("Comando equipment ainda por implementar.")

"""Funções reservadas às alíneas a), b), c) e d)."""

from typing import Any

from . import api, processing


def top_exercises(limit: int) -> list[dict[str, Any]]:
    """TODO a): obter os N exercícios mais recentes em inglês."""
    raise NotImplementedError("Comando top ainda por implementar.")


def search_exercises(target: str, limit: int) -> list[dict[str, Any]]:
    """TODO b): pesquisar por músculo e/ou categoria e limitar os resultados."""
    raise NotImplementedError("Comando search ainda por implementar.")


def exercise_type(exercise_id: int) -> str:
    """TODO c): inferir o esforço pela descrição, categoria e músculos."""
    raise NotImplementedError("Comando type ainda por implementar.")


def equipment_frequency(category: str) -> list[dict[str, Any]]:
    """TODO d): extrair equipamento com re e ordenar por frequência."""
    raise NotImplementedError("Comando equipment ainda por implementar.")

"""Pontos de implementação para limpeza e classificação com expressões regulares."""

import re
from typing import Any

HTML_TAGS = re.compile(r"<[^>]+>")
EQUIPMENT_PATTERN = re.compile(r"\b(barbell|dumbbell|cable|machine|bodyweight)\b", re.I)


def clean_description(description: str) -> str:
    """TODO: remover HTML e normalizar os espaços da descrição."""
    raise NotImplementedError("Limpeza de descrições ainda por implementar.")


def classify_effort(exercise: dict[str, Any]) -> str:
    """TODO: definir regras para compound, isolated, cardio e other."""
    raise NotImplementedError("Classificação de esforço ainda por implementar.")


def count_equipment(descriptions: list[str]) -> list[dict[str, Any]]:
    """TODO: devolver equipment/count por frequência decrescente usando re."""
    raise NotImplementedError("Contagem de equipamento ainda por implementar.")

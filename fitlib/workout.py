"""Composição das operações anteriores para a alínea e)."""

from enum import Enum
from typing import Any

from . import exercises


class Effort(str, Enum):
    compound = "compound"
    isolated = "isolated"
    any = "any"


def build_workout(targets: str, effort: Effort, limit: int) -> dict[str, list[dict[str, Any]]]:
    """TODO e): separar alvos por vírgula e reutilizar pesquisa/classificação."""
    raise NotImplementedError("Comando workout ainda por implementar.")

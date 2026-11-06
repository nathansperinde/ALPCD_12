"""Funções reservadas à serialização JSON e à exportação CSV."""

import csv
import json
from pathlib import Path
from typing import Any


def print_json(data: Any) -> None:
    """TODO: apresentar os dados em JSON no terminal."""
    raise NotImplementedError("Saída JSON ainda por implementar.")


def write_workout_csv(workout: dict[str, list[dict[str, Any]]], path: Path) -> None:
    """TODO: exportar o plano de treino com cabeçalhos e codificação UTF-8."""
    raise NotImplementedError("Exportação CSV ainda por implementar.")

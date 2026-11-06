"""Saída JSON e exportação de planos de treino para CSV."""

import csv
import json
from pathlib import Path
from typing import Any

CSV_FIELDS = ("target", "id", "name", "category", "equipment", "type")


def print_json(data: Any) -> None:
    """Imprimir JSON indentado, preservando acentos e terminando com newline."""
    print(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False))


def _csv_value(value: Any) -> Any:
    """Representar estruturas numa célula sem perder os seus campos."""
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, allow_nan=False)
    return value


def write_workout_csv(workout: dict[str, list[dict[str, Any]]], path: Path) -> None:
    """Escrever uma linha por exercício, com o alvo e as colunas CSV_FIELDS.

    Campos ausentes ficam vazios; campos adicionais são ignorados. Listas e
    objetos (por exemplo equipment) são JSON dentro da célula. Mesmo um plano
    vazio gera o cabeçalho. A pasta de destino deve existir; o ficheiro é
    substituído, e erros de escrita propagam-se como OSError.
    """
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

from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Any

import typer

from fitlib import exercises, extras
from fitlib.exercises import build_workout


# [BASE] CONFIGURAÇÃO
# Interface Typer e argumentos partilhados

app = typer.Typer(help="Consulta de exercícios wger — ALPCD, Grupo 12.", no_args_is_help=True)
PositiveInt = Annotated[int, typer.Argument(min=1)]
Target = Annotated[str, typer.Argument(help="Músculo e/ou categoria.")]


# [BASE] EXECUÇÃO
# Apresentação de resultados e tratamento de erros

def run_action(action: Callable[[], Any], *, as_json: bool = True, show_count: bool = False) -> None:
    try:
        result = action()
        if show_count and isinstance(result, list):
            typer.echo(f"Total de exercícios exibidos: {len(result)}\n", err=True)
        if as_json:
            exercises.print_json(result)
        elif result is not None:
            typer.echo(result)
    except (RuntimeError, OSError, ValueError) as exc:
        typer.echo(f"Erro: {exc}", err=True)
        raise typer.Exit(code=1) from exc


# [A] TOP
# Exercícios mais recentes

@app.command()
def top(
    n: PositiveInt,
    refresh: Annotated[bool, typer.Option("--refresh", help="Ignorar a cache.")] = False,
) -> None:
    """a) Mostrar os N exercícios mais recentes."""
    run_action(lambda: exercises.top_exercises(n, refresh=refresh))


# [B] SEARCH
# Pesquisa por músculo ou categoria

@app.command()
def search(
    target: Target,
    n: PositiveInt,
    refresh: Annotated[bool, typer.Option("--refresh", help="Ignorar a cache.")] = False,
) -> None:
    """b) Pesquisar exercícios por músculo e/ou categoria."""
    if not target.strip():
        raise typer.BadParameter("Indique um músculo ou uma categoria.", param_hint="target")
    run_action(lambda: exercises.search_exercises(target, n, refresh=refresh))


# [C] TYPE
# Classificação do esforço

@app.command(name="type")
def exercise_type(
    exercise_id: Annotated[str, typer.Argument(help="ID ou palavras com --find.")],
    find: Annotated[bool, typer.Option("--find")] = False,
    deep: Annotated[bool, typer.Option("--deep")] = False,
    limit: Annotated[int, typer.Option("--limit", min=1)] = 20
) -> None:
    """c) Inferir o tipo de esforço de um exercício."""
    if find:
        run_action(lambda: extras.search_exercise_types(exercise_id, limit, deep), show_count=True)
    else:
        if not exercise_id.isdecimal() or int(exercise_id) <= 0:
            raise typer.BadParameter("Indique um ID positivo ou utilize --find")
        run_action(lambda: exercises.exercise_type(int(exercise_id)), as_json=False)


# [D] EQUIPMENT
# Frequência de equipamentos

@app.command()
def equipment(
    category: Annotated[
        str, typer.Argument(help="Nome da categoria em inglês (ex.: chest, back, legs).")
    ],
) -> None:
    """d) Contar menções a equipamento nas descrições e apresentar JSON."""
    category = category.strip()
    if not category:
        raise typer.BadParameter("Indique uma categoria não vazia.", param_hint="category")
    run_action(lambda: exercises.equipment_frequency(category))


# [X1] FIND
# Pesquisa textual de exercícios

@app.command()
def find(
    query: Annotated[str, typer.Argument(help="Texto a pesquisar.")],
    limit: Annotated[int, typer.Option("--limit", min=1)] = 20,
    deep: Annotated[bool, typer.Option("--deep")] = False,
    show_description: Annotated[
        bool, typer.Option("--description")
    ] = False
) -> None:
    """Extra 1: Pesquisar exercício por palavra(s) no nome e/ou na descrição"""
    run_action(lambda: extras.find_exercises(query, limit, deep, show_description), show_count=True)


# [X2] COMPARE
# Comparação de exercícios

@app.command()
def compare(
    ids: Annotated[
        list[int],
        typer.Argument(help="IDs dos exercícios a comparar.")
    ]
) -> None:
    """Extra 2: Comparar dois ou mais exercícios."""
    run_action(lambda: extras.compare_exercises(ids))


# [E] WORKOUT
# Criação de planos de treino
# Plano local; não usa os templates/rotinas do TCLI.

@app.command()
def workout(
    targets: Annotated[str, typer.Argument(help="Alvos separados por vírgula.")],
    effort: Annotated[str, typer.Argument(help="compound, isolated ou any.")],
    n: PositiveInt,
    csv_path: Annotated[Path | None, typer.Option("--csv", help="Exportar para CSV.")] = None,
) -> None:
    """e) Preparar um plano de treino por alvo e tipo de esforço."""
    if effort not in ("compound", "isolated", "any"):
        raise typer.BadParameter("Indique compound, isolated ou any.", param_hint="effort")
    if not targets.strip() or any(not target.strip() for target in targets.split(",")):
        raise typer.BadParameter("Indique alvos não vazios separados por vírgula.", param_hint="targets")

    def action() -> Any:
        plan = build_workout(targets, effort, n)
        if csv_path is not None:
            exercises.write_workout_csv(plan, csv_path)
            total = 0
            for items in plan.values():
                total += len(items)
            typer.echo(f"Ficheiro exportado: {csv_path} ({total} registos)")
            return None
        return plan

    run_action(action, as_json=csv_path is None)


# [X3] DIFFICULTY
# Estimativa de dificuldade

@app.command()
def difficulty(
    exercise_id: int = typer.Argument(..., min=1, help="ID do exercício."),
    refresh: bool = typer.Option(False, "--refresh", help="Ignorar a cache."),
):
    """Extra: estimar o nível de dificuldade de um exercício."""
    run_action(lambda: extras.exercise_difficulty(exercise_id, refresh=refresh))


# [X4] INGREDIENT
# Consulta de valores nutricionais

@app.command()
def ingredient(
    name: str = typer.Argument(..., help="Nome do ingrediente (em inglês)."),
    limit: int = typer.Option(5, "--limit", min=1, max=20),
    grams: float = typer.Option(100.0, "--grams", min=1),
    refresh: bool = typer.Option(False, "--refresh", help="Ignorar a cache."),
):
    """Extra: calorias e macronutrientes de um ingrediente."""
    run_action(lambda: extras.ingredient_info(name, limit, grams, refresh=refresh))


if __name__ == "__main__":
    app()

"""CLI do TP1: A/B integradas; as restantes alíneas mantêm-se por implementar."""

from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Any

import typer

from fitlib import exercises, output
from fitlib.workout import Effort, build_workout

app = typer.Typer(help="Consulta de exercícios wger — ALPCD, Grupo 12.", no_args_is_help=True)
PositiveInt = Annotated[int, typer.Argument(min=1)]
Target = Annotated[str, typer.Argument(help="Músculo e/ou categoria.")]


def run_action(action: Callable[[], Any], *, as_json: bool = True, show_count: bool = False) -> None:
    try:
        result = action()
        if show_count and isinstance(result, list):
            typer.echo(f"Total de exercícios exibidos: {len(result)}\n", err=True)
        if as_json:
            output.print_json(result)
        elif result is not None:
            typer.echo(result)
    except NotImplementedError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    except (RuntimeError, OSError, ValueError) as exc:
        typer.echo(f"Erro: {exc}", err=True)
        raise typer.Exit(code=1) from exc


@app.command()
def top(
    n: PositiveInt,
    refresh: Annotated[bool, typer.Option("--refresh", help="Ignorar a cache.")] = False,
) -> None:
    """a) Mostrar os N exercícios mais recentes."""
    # A de Rafael: regras em exercises; JSON pelo output original via run_action.
    run_action(lambda: exercises.top_exercises(n, refresh=refresh))


@app.command()
def search(
    target: Target,
    n: PositiveInt,
    refresh: Annotated[bool, typer.Option("--refresh", help="Ignorar a cache.")] = False,
) -> None:
    """b) Pesquisar exercícios por músculo e/ou categoria."""
    if not target.strip():
        raise typer.BadParameter("Indique um músculo ou uma categoria.", param_hint="target")
    # B de Rafael: resolver filtros e deduplicar no domínio, sem uma CLI paralela.
    run_action(lambda: exercises.search_exercises(target, n, refresh=refresh))


@app.command(name="type")
def exercise_type(
    exercise_id: Annotated[str, typer.Argument(help="ID ou palavras com --find.")],
    find: Annotated[bool, typer.Option("--find")] = False,
    deep: Annotated[bool, typer.Option("--deep")] = False,
    limit: Annotated[int, typer.Option("--limit", min=1)] = 20
) -> None:
    """c) Inferir o tipo de esforço de um exercício."""
    if find:
        run_action(lambda: exercises.search_exercise_types(exercise_id, limit, deep), show_count=True)
    else:
        if not exercise_id.isdecimal() or int(exercise_id) <= 0:
            raise typer.BadParameter("Indique um ID positivo ou utilize --find")
        run_action(lambda: exercises.exercise_type(int(exercise_id)), as_json=False)


@app.command()
def equipment(category: Target) -> None:
    """d) Contar menções a equipamento numa categoria."""
    run_action(lambda: exercises.equipment_frequency(category))


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
    run_action(lambda: exercises.find_exercises(query, limit, deep, show_description), show_count=True)


@app.command()
def compare(
    ids: Annotated[
        list[int],
        typer.Argument(help="IDs dos exercícios a comparar.")
    ]
) -> None:
    """Extra 2: Comparar dois ou mais exercícios."""
    run_action(lambda: exercises.compare_exercises(ids))


@app.command()
def workout(
    targets: Annotated[str, typer.Argument(help="Alvos separados por vírgula.")],
    effort: Effort,
    n: PositiveInt,
    csv_path: Annotated[Path | None, typer.Option("--csv", help="Exportar para CSV.")] = None,
) -> None:
    """e) Preparar um plano de treino por alvo e tipo de esforço."""
    if not targets.strip() or any(not target.strip() for target in targets.split(",")):
        raise typer.BadParameter("Indique alvos não vazios separados por vírgula.", param_hint="targets")

    def action() -> Any:
        plan = build_workout(targets, effort, n)
        if csv_path is not None:
            output.write_workout_csv(plan, csv_path)
            return None
        return plan

    run_action(action, as_json=csv_path is None)


if __name__ == "__main__":
    app()

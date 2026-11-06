"""CLI do TP1: comandos preparados para implementação pelo grupo."""

from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Any

import typer

from fitlib import exercises, output
from fitlib.workout import Effort, build_workout

app = typer.Typer(help="Consulta de exercícios wger — ALPCD, Grupo 12.", no_args_is_help=True)
PositiveInt = Annotated[int, typer.Argument(min=1)]
Target = Annotated[str, typer.Argument(help="Músculo e/ou categoria.")]


def run_action(action: Callable[[], Any], *, as_json: bool = True) -> None:
    try:
        result = action()
        if as_json:
            output.print_json(result)
        elif result is not None:
            typer.echo(result)
    except NotImplementedError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc


@app.command()
def top(n: PositiveInt) -> None:
    """a) Mostrar os N exercícios mais recentes."""
    run_action(lambda: exercises.top_exercises(n))


@app.command()
def search(target: Target, n: PositiveInt) -> None:
    """b) Pesquisar exercícios por músculo e/ou categoria."""
    run_action(lambda: exercises.search_exercises(target, n))


@app.command(name="type")
def exercise_type(exercise_id: PositiveInt) -> None:
    """c) Inferir o tipo de esforço de um exercício."""
    run_action(lambda: exercises.exercise_type(exercise_id), as_json=False)


@app.command()
def equipment(category: Target) -> None:
    """d) Contar menções a equipamento numa categoria."""
    run_action(lambda: exercises.equipment_frequency(category))


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

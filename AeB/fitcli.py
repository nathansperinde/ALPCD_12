"""CLI de exercício físico sobre a API wger."""

import json
import re

import typer

from api import LANGUAGE, get_list

app = typer.Typer(help="Pesquisa de exercícios na API wger.")


def _name_in_english(exercise: dict) -> str | None:
    for translation in exercise.get("translations", []):
        if translation.get("language") == LANGUAGE and translation.get("name"):
            return translation["name"]
    return None


def _format(exercise: dict) -> dict | None:
    """Reduzir um exercício da API ao formato de saída; None se sem nome inglês."""
    name = _name_in_english(exercise)
    if name is None:
        return None
    category = (exercise.get("category") or {}).get("name")
    equipment = [e.get("name") for e in exercise.get("equipment", [])]
    muscles = [m.get("name_en") or m.get("name") for m in exercise.get("muscles", [])]
    return {"name": name, "category": category, "equipment": equipment, "muscles": muscles}


def _print_json(data) -> None:
    typer.echo(json.dumps(data, indent=2, ensure_ascii=False))


def _fail(message: str) -> None:
    typer.echo(f"Erro: {message}", err=True)
    raise typer.Exit(code=1)


@app.command()
def top(
    n: int = typer.Argument(..., min=1, help="Número de exercícios a listar."),
    refresh: bool = typer.Option(False, "--refresh", help="Ignorar a cache."),
):
    """a) Listar os N exercícios mais recentes (em inglês)."""
    params = {"language": LANGUAGE, "ordering": "-created", "limit": min(n, 100)}
    try:
        exercises = get_list("exerciseinfo/", params, max_items=n,
                             refresh=refresh, transform=_format)
    except RuntimeError as exc:
        _fail(str(exc))
    _print_json(exercises)


def _matching_ids(items: list[dict], pattern: re.Pattern) -> list[int]:
    return [
        item["id"] for item in items
        if pattern.search(item.get("name_en") or "") or pattern.search(item.get("name") or "")
    ]


@app.command()
def search(
    term: str = typer.Argument(..., help="Nome do músculo ou da categoria."),
    n: int = typer.Argument(..., min=1, help="Número máximo de resultados."),
    refresh: bool = typer.Option(False, "--refresh", help="Ignorar a cache."),
):
    """b) Pesquisar exercícios por músculo e/ou categoria."""
    pattern = re.compile(re.escape(term.strip()), re.IGNORECASE)
    try:
        muscles = get_list("muscle/", {"limit": 100}, refresh=refresh)
        categories = get_list("exercisecategory/", {"limit": 100}, refresh=refresh)

        filters = [("muscles", i) for i in _matching_ids(muscles, pattern)]
        filters += [("category", i) for i in _matching_ids(categories, pattern)]
        if not filters:
            _fail(f"'{term}' não corresponde a nenhum músculo nem categoria.")

        seen: set[str] = set()   # evitar repetidos quando há várias correspondências

        def unique(exercise: dict) -> dict | None:
            formatted = _format(exercise)
            if formatted is None or formatted["name"] in seen:
                return None
            seen.add(formatted["name"])
            return formatted

        results: list[dict] = []
        for field, ident in filters:
            if len(results) >= n:
                break
            params = {"language": LANGUAGE, field: ident, "limit": min(n, 100)}
            results += get_list("exerciseinfo/", params,
                                max_items=n - len(results),
                                refresh=refresh, transform=unique)
    except typer.Exit:
        raise  # typer.Exit é um RuntimeError: não deixar o `except` abaixo apanhá-lo
    except RuntimeError as exc:
        _fail(str(exc))
    _print_json(results)


if __name__ == "__main__":
    app()

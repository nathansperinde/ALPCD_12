"""Pedidos JSON e paginação da API pública wger."""

from typing import Any
from urllib.parse import urljoin, urlparse

import requests

BASE_URL = "https://wger.de/api/v2/"
LANGUAGE = 2
TIMEOUT = 30

session = requests.Session()
session.headers.update({"User-Agent": "ALPCD-Grupo12/0.1", "Accept": "application/json"})


def _url(endpoint: str) -> str:
    """Aceitar caminhos relativos ou URLs de paginação da mesma API."""
    url = urljoin(BASE_URL, endpoint)
    base, parsed = urlparse(BASE_URL), urlparse(url)
    if (
        (parsed.scheme, parsed.netloc) != (base.scheme, base.netloc)
        or not parsed.path.startswith(base.path)
    ):
        raise RuntimeError("O endpoint deve pertencer à URL base da API.")
    return url


def get_json(endpoint: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """Obter um objeto JSON; lançar RuntimeError em falhas HTTP, rede ou formato.

    Os parâmetros não são alterados. O idioma deve ser passado explicitamente
    nos pedidos de exercícios: params={"language": LANGUAGE}.
    """
    url = _url(endpoint)
    try:
        response = session.get(url, params=params, timeout=TIMEOUT)
        response.raise_for_status()
    except requests.Timeout as exc:
        raise RuntimeError("A API excedeu o tempo limite do pedido.") from exc
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else "desconhecido"
        raise RuntimeError(f"A API devolveu o erro HTTP {status}.") from exc
    except requests.RequestException as exc:
        raise RuntimeError("Não foi possível comunicar com a API.") from exc
    try:
        data = response.json()
    except ValueError as exc:
        raise RuntimeError("A API não devolveu JSON válido.") from exc
    if not isinstance(data, dict):
        raise RuntimeError("Era esperado um objeto JSON da API.")
    return data


def get_all(endpoint: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Reunir results de todas as páginas, seguindo next até None.

    Os filtros são enviados apenas na primeira página: as URLs next já os
    contêm. A ordem e os campos devolvidos pela API são preservados.
    """
    results: list[dict[str, Any]] = []
    url: str | None = _url(endpoint)
    visited: set[str] = set()
    while url is not None:
        if url in visited:
            raise RuntimeError("A API devolveu um ciclo na paginação.")
        visited.add(url)
        page = get_json(url, params=params)
        items = page.get("results")
        if not isinstance(items, list) or any(not isinstance(item, dict) for item in items):
            raise RuntimeError("A página da API deve conter uma lista results de objetos.")
        results.extend(items)
        next_page = page.get("next")
        if next_page is not None and (not isinstance(next_page, str) or not next_page):
            raise RuntimeError("O campo next da API deve ser uma URL ou null.")
        url = _url(urljoin(url, next_page)) if next_page is not None else None
        params = None
    return results

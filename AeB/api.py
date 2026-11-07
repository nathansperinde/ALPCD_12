"""Pedidos JSON, cache e paginação da API pública wger."""

import json
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urljoin, urlparse

import requests

BASE_URL = "https://wger.de/api/v2/"
LANGUAGE = 2  # inglês
TIMEOUT = 30
CACHE_FILE = Path(__file__).with_name("cache.json")
HEADERS = {"User-Agent": "ALPCD-Grupo12/0.1", "Accept": "application/json"}

session = requests.Session()
session.headers.update(HEADERS)


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


def _cache_key(url: str, params: dict | None) -> str:
    return url + "|" + json.dumps(params or {}, sort_keys=True)


def _load_cache() -> dict:
    try:
        with CACHE_FILE.open("r", encoding="utf-8") as file:
            cache = json.load(file)
    except (OSError, json.JSONDecodeError):
        return {}
    return cache if isinstance(cache, dict) else {}


def _save_cache(cache: dict) -> None:
    try:
        with CACHE_FILE.open("w", encoding="utf-8") as file:
            json.dump(cache, file, ensure_ascii=False)
    except OSError:
        pass  # a cache é opcional: falhar a gravar não deve parar o programa


def _request(url: str, params: dict | None) -> dict:
    """Fazer um pedido GET e devolver um objeto JSON."""
    try:
        response = session.get(url, params=params, timeout=TIMEOUT)
        response.raise_for_status()
        data = response.json()
    except requests.Timeout as exc:
        raise RuntimeError("A API excedeu o tempo limite do pedido.") from exc
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else "desconhecido"
        raise RuntimeError(f"A API devolveu o erro HTTP {status}.") from exc
    except requests.RequestException as exc:
        raise RuntimeError("Não foi possível comunicar com a API.") from exc
    except ValueError as exc:
        raise RuntimeError("A API não devolveu JSON válido.") from exc

    if not isinstance(data, dict):
        raise RuntimeError("Era esperado um objeto JSON da API.")
    return data


def get_json(endpoint: str, params: dict[str, Any] | None = None,
             refresh: bool = False) -> dict[str, Any]:
    """Obter um objeto JSON (com cache). Lança RuntimeError em qualquer falha."""
    url = _url(endpoint)
    key = _cache_key(url, params)
    cache = _load_cache()

    if not refresh and isinstance(cache.get(key), dict):
        return cache[key]

    data = _request(url, params)
    cache[key] = data
    _save_cache(cache)
    return data


def get_list(
    endpoint: str,
    params: dict[str, Any] | None = None,
    max_items: int | None = None,
    refresh: bool = False,
    transform: Callable[[dict], Any] | None = None,
) -> list:
    """Reunir `results` de várias páginas, seguindo `next` até None.

    `transform` (opcional) é aplicado a cada item; se devolver None, o item é
    descartado. O limite `max_items` conta apenas os itens que ficam.
    """
    if max_items is not None and max_items <= 0:
        raise ValueError("max_items deve ser positivo.")

    results: list = []
    url: str | None = _url(endpoint)
    visited: set[str] = set()

    while url is not None:
        if url in visited:
            raise RuntimeError("A API devolveu um ciclo na paginação.")
        visited.add(url)

        page = get_json(url, params=params, refresh=refresh)
        items = page.get("results")
        if not isinstance(items, list):
            raise RuntimeError("A página da API deve conter uma lista results.")

        for item in items:
            if not isinstance(item, dict):
                raise RuntimeError("Os results devem ser objetos JSON.")
            if transform is not None:
                item = transform(item)
                if item is None:
                    continue
            results.append(item)
            if max_items is not None and len(results) >= max_items:
                return results

        next_page = page.get("next")
        if next_page is not None and not isinstance(next_page, str):
            raise RuntimeError("O campo next da API deve ser uma URL ou null.")
        url = _url(urljoin(url, next_page)) if next_page else None
        params = None  # os filtros já vêm dentro da URL next

    return results

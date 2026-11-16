import json
import tempfile
import time
from pathlib import Path

import requests


BASE_URL = "https://wger.de/api/v2/"
CACHE_FILE = Path(__file__).with_name("cache.json")
CACHE_TTL = 14 * 24 * 60 * 60
_memory_cache = {}
HEADERS = {
    "User-Agent": "ALPCD-Grupo12/0.1",
    "Accept": "application/json"
}
HTTP_ERRORS = {
    400: "Bad request.",
    401: "Authentication required.",
    403: "Access forbidden.",
    404: "Resource not found.",
    408: "Request timeout.",
    429: "Too many requests."
}


def _load_cache() -> dict:
    cache = {}
    if CACHE_FILE.exists():
        try:
            with CACHE_FILE.open("r", encoding="utf-8") as file:
                cache = json.load(file)
        except (OSError, json.JSONDecodeError):
            cache = {}

    if not isinstance(cache, dict):
        cache = {}
    return cache


def _cache_key(endpoint: str, params: dict | None) -> str:
    return endpoint + "|" + json.dumps(params or {}, sort_keys=True)


def _get_cached_data(cache: dict, key: str) -> dict | None:
    saved = cache.get(key)
    if not isinstance(saved, dict):
        cache.pop(key, None)
        return None

    expires_at = saved.get("expires_at")
    if (type(expires_at) not in (int, float)
            or not time.time() < expires_at < float("inf")):
        cache.pop(key, None)
        return None

    data = saved.get("data")
    if isinstance(data, dict):
        return data
    cache.pop(key, None)
    return None


def _build_url(endpoint: str) -> str:
    if endpoint.startswith("https://"):
        if not endpoint.startswith(BASE_URL):
            raise ValueError("Only wger API URLs are allowed.")
        return endpoint
    return BASE_URL + endpoint.lstrip("/")


def request(method, endpoint, token, data=None):
    """Pedido autenticado sem cache; GET usa parâmetros, POST/PATCH usam JSON."""
    url = _build_url(endpoint)
    payload = {"params": data} if method == "GET" else {"json": data}
    try:
        response = requests.request(
            method, url, headers={**HEADERS, "Authorization": f"Bearer {token}"},
            timeout=15, **payload,
        )
        response.raise_for_status()
        result = response.json()
        if not isinstance(result, dict) or (method != "GET" and "id" not in result):
            raise ValueError("Resposta inválida.")
        return result
    except requests.exceptions.RequestException as error:
        status = error.response.status_code if error.response is not None else "rede"
        message = f"Falha no pedido {method} {url.split('?')[0]} (HTTP {status})."
        if error.response is not None and status == 403:
            try:
                code = error.response.json().get("code")
            except ValueError:
                code = None
            message += (" Sessão expirada ou token inválido." if code == "token_not_valid"
                        else " Acesso recusado pela wger; verifique autenticação e permissões.")
        raise RuntimeError(message) from error
    except ValueError as error:
        raise RuntimeError("Resposta JSON inválida.") from error


def _request_data(url: str, params: dict | None) -> dict:
    try:
        response = requests.get(
            url,
            params=params,
            headers=HEADERS,
            timeout=15
        )

        response.raise_for_status()

        data = response.json()

        if not isinstance(data, dict):
            raise RuntimeError("The API did not return a JSON object.")

        return data

    except requests.exceptions.HTTPError as error:
        status = error.response.status_code

        message = HTTP_ERRORS.get(
            status,
            "Server error." if status >= 500 else "HTTP error."
        )

        raise RuntimeError(f"HTTP {status}: {message}") from error

    except requests.exceptions.Timeout as error:
        raise RuntimeError("The request timed out.") from error

    except requests.exceptions.ConnectionError as error:
        raise RuntimeError("Connection error.") from error

    except ValueError as error:
        raise RuntimeError("Invalid JSON response.") from error

    except requests.exceptions.RequestException as error:
        raise RuntimeError("Request failed.") from error


def _write_cache(cache: dict) -> None:
    """Replace the JSON file atomically using a temporary file."""
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=CACHE_FILE.parent,
            prefix=CACHE_FILE.name + ".", suffix=".tmp", delete=False,
        ) as file:
            temporary_path = Path(file.name)
            json.dump(cache, file, indent=2, ensure_ascii=False)
        temporary_path.replace(CACHE_FILE)
    except OSError as error:
        raise RuntimeError("Failed to save cache.") from error
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def _save_cache(cache: dict, key: str, data: dict, cache_mode: str = "disk") -> None:
    # Remove expired or invalid entries before adding the fresh result.
    for saved_key in list(cache):
        _get_cached_data(cache, saved_key)

    cache[key] = {"data": data, "expires_at": time.time() + CACHE_TTL}
    if cache_mode == "disk":
        _write_cache(cache)


def get_data(
    endpoint: str, params: dict | None = None, refresh: bool = False,
    *, cache_mode: str = "disk",
) -> dict:
    """Fetch using none, memory or disk caching; cached entries last 14 days."""
    if cache_mode not in ("none", "disk", "memory"):
        raise ValueError("cache_mode must be 'none', 'disk', or 'memory'.")
    url = _build_url(endpoint)
    if cache_mode == "none":
        return _request_data(url, params)

    cache = _load_cache() if cache_mode == "disk" else _memory_cache
    key = _cache_key(endpoint, params)
    if not refresh:
        saved = _get_cached_data(cache, key)
        if saved is not None:
            return saved

    data = _request_data(url, params)
    _save_cache(cache, key, data, cache_mode)
    return data


def get_list(
    endpoint: str,
    params: dict | None = None,
    max_items: int | None = None,
    refresh: bool = False,
    transform=None,
    *,
    cache_mode: str = "disk",
    token: str | None = None,
) -> list[dict]:
    """Paginar; quando indicado, contar apenas os itens aceites por transform."""
    if max_items is not None and max_items <= 0:
        raise ValueError("max_items must be positive.")

    items = []
    url = endpoint
    visited = []

    while url:
        if url in visited:
            raise RuntimeError("Pagination loop detected.")

        visited.append(url)

        if token is None:
            page = get_data(url, params, refresh, cache_mode=cache_mode)
        else:
            page = request("GET", url, token, params)

        if not isinstance(page, dict) or not isinstance(page.get("results"), list):
            raise RuntimeError("The API did not return a valid results list.")

        # Contar apenas os itens aceites pela transformação.
        # Sem transformação, manter todos os itens da página.
        for item in page["results"]:
            if transform is not None:
                item = transform(item)
                if item is None:
                    continue
            items.append(item)

            if max_items is not None and len(items) >= max_items:
                return items[:max_items]

        url = page.get("next")
        params = None

    return items

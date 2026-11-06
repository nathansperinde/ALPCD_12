import json
from pathlib import Path

import requests

BASE_URL = "https://wger.de/api/v2/"
CACHE_FILE = Path(__file__).with_name("cache.json")
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
        return None

    if (isinstance(saved.get("results"), list)
            and "next" in saved and "count" in saved):
        return saved
    if "id" in saved:
        return saved
    return None


def _build_url(endpoint: str) -> str:
    if endpoint.startswith("https://"):
        if not endpoint.startswith(BASE_URL):
            raise ValueError("Only wger API URLs are allowed.")
        return endpoint
    return BASE_URL + endpoint.lstrip("/")



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


def _save_cache(cache: dict, key: str, data: dict) -> None:
    cache[key] = data

    try:
        with CACHE_FILE.open("w", encoding="utf-8") as file:
            json.dump(cache, file, indent=2, ensure_ascii=False)

    except OSError as error:
        raise RuntimeError("Failed to save cache.") from error


def get_data(endpoint: str, params: dict | None = None, refresh: bool = False) -> dict:
    cache = _load_cache()
    key = _cache_key(endpoint, params)

    if not refresh:
        saved = _get_cached_data(cache, key)
        if saved is not None:
            return saved

    data = _request_data(_build_url(endpoint), params)
    _save_cache(cache, key, data)
    return data



def get_list(endpoint: str, params: dict | None = None, max_items: int | None = None, refresh: bool = False) -> list[dict]:
    if max_items is not None and max_items <= 0:
        raise ValueError("max_items must be positive.")

    items = []
    url = endpoint
    visited = []

    while url:
        if url in visited:
            raise RuntimeError("Pagination loop detected.")

        visited.append(url)

        page = get_data(url, params, refresh)

        if not isinstance(page, dict) or not isinstance(page.get("results"), list):
            raise RuntimeError("The API did not return a valid results list.")

        items.extend(page["results"])

        if max_items is not None and len(items) >= max_items:
            return items[:max_items]

        url = page.get("next")
        params = None

    return items

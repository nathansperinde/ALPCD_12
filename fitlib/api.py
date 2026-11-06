"""Configuração HTTP e pontos de implementação dos pedidos à API wger."""

from typing import Any

import requests

BASE_URL = "https://wger.de/api/v2/"
LANGUAGE = 2
TIMEOUT = 30

session = requests.Session()
session.headers.update({"User-Agent": "ALPCD-Grupo12/0.1"})


def get_json(endpoint: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """TODO: fazer o pedido com timeout, verificar o status e descodificar JSON."""
    raise NotImplementedError("Pedidos à API ainda por implementar.")


def get_all(endpoint: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """TODO: percorrer a paginação e reunir todos os resultados."""
    raise NotImplementedError("Paginação ainda por implementar.")

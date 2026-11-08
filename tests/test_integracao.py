"""Regressões da integração Nathan + Rafael, sem pedidos à Internet."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import requests
from typer.testing import CliRunner

from fitcli import app
from fitlib import api, exercises


def raw_exercise(ident, name="Curl", language=2):
    return {
        "id": ident,
        "translations": [{"language": language, "name": name, "description": "<p>Curl.</p>"}],
        "category": {"id": 1, "name": "Arms"},
        "equipment": [{"id": 1, "name": "Dumbbell"}],
        "muscles": [{"id": 1, "name": "Biceps brachii", "name_en": "Biceps"}],
        "muscles_secondary": [{"id": 2, "name": "Forearm", "name_en": ""}],
    }


class IntegrationTests(unittest.TestCase):
    def test_build_url_accepts_endpoints_and_real_pagination_urls(self):
        absolute = api.BASE_URL + "exerciseinfo/?limit=1&offset=1"
        self.assertEqual(api._build_url("exerciseinfo/"), api.BASE_URL + "exerciseinfo/")
        self.assertEqual(api._build_url(absolute), absolute)
        with self.assertRaises(ValueError):
            api._build_url("https://example.com/api/v2/exerciseinfo/")

    def test_transform_counts_accepted_items_across_pages(self):
        next_url = api.BASE_URL + "exerciseinfo/?offset=2"
        pages = [
            {"results": [raw_exercise(1, language=1), raw_exercise(2)], "next": next_url},
            {"results": [raw_exercise(3), raw_exercise(4)], "next": None},
        ]
        with patch.object(api, "get_data", side_effect=pages) as request:
            result = api.get_list("exerciseinfo/", {"language": 2}, 2, True, exercises._format)
        self.assertEqual([item["id"] for item in result], [2, 3])
        self.assertEqual(request.call_args_list[1].args, (next_url, None, True))

    def test_pagination_without_transform_keeps_original_results(self):
        data = [{"id": 1}, {"id": 2}, {"id": 3}]
        with patch.object(api, "get_data", return_value={"results": data, "next": None}):
            self.assertEqual(api.get_list("exerciseinfo/", max_items=2), data[:2])
        with patch.object(api, "get_data", return_value={"results": data, "next": None}):
            self.assertEqual(api.get_list("exerciseinfo/"), data)

    def test_transform_handles_exhaustion_cycles_and_invalid_limit(self):
        with patch.object(api, "get_data", return_value={"results": [{"id": 1}], "next": None}):
            self.assertEqual(api.get_list("exerciseinfo/", transform=lambda item: None), [])
        with patch.object(api, "get_data", return_value={"results": [], "next": "exerciseinfo/"}):
            with self.assertRaisesRegex(RuntimeError, "loop"):
                api.get_list("exerciseinfo/", transform=lambda item: None)
        with self.assertRaises(ValueError):
            api.get_list("exerciseinfo/", max_items=0)

    def test_format_preserves_id_description_and_secondary_muscles(self):
        result = exercises._format(raw_exercise(10))
        self.assertEqual(result["id"], 10)
        self.assertEqual(result["description"], "<p>Curl.</p>")
        self.assertEqual(result["muscles_secondary"], ["Forearm"])
        self.assertEqual(result["equipment"], ["Dumbbell"])
        self.assertIsNone(exercises._format(raw_exercise(10, language=1)))

    def test_search_deduplicates_ids_across_filters_and_pages_not_names(self):
        # "arms" corresponde a um músculo e a uma categoria. Nomes iguais com
        # IDs diferentes devem ficar; o mesmo ID noutra página/filtro deve sair.
        responses = {
            "muscle/": {"results": [{"id": 1, "name_en": "Arms"}], "next": None},
            "exercisecategory/": {"results": [{"id": 1, "name": "Arms"}], "next": None},
            "page2": {"results": [raw_exercise(1), raw_exercise(2)], "next": None},
        }

        def get_data(endpoint, params, refresh):
            if endpoint in responses:
                return responses[endpoint]
            if "muscles" in params:
                return {"results": [raw_exercise(1)], "next": "page2"}
            return {"results": [raw_exercise(2), raw_exercise(3)], "next": None}

        with patch.object(api, "get_data", side_effect=get_data):
            result = exercises.search_exercises("arms", 3)
        self.assertEqual([item["id"] for item in result], [1, 2, 3])
        self.assertEqual([item["name"] for item in result], ["Curl"] * 3)

    def test_search_rejects_empty_term_and_treats_regex_literally(self):
        with patch.object(api, "get_list") as query:
            with self.assertRaises(ValueError):
                exercises.search_exercises("   ", 5)
            query.assert_not_called()
        with patch.object(api, "get_list", return_value=[{"id": 1, "name": "Arms"}]):
            with self.assertRaisesRegex(RuntimeError, "não corresponde"):
                exercises.search_exercises(".*", 5)

    def test_cli_refresh_reaches_nathan_api_and_outputs_json(self):
        runner = CliRunner()
        with patch.object(api, "get_data", return_value={"results": [raw_exercise(1)], "next": None}) as query:
            result = runner.invoke(app, ["top", "1", "--refresh"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(json.loads(result.output)[0]["id"], 1)
        self.assertEqual(query.call_args.args[2], True)
        self.assertEqual(runner.invoke(app, ["search", "   ", "5"]).exit_code, 2)

    def test_original_cache_refresh_and_json_error_classification(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(api, "CACHE_FILE", Path(directory) / "cache.json"):
                with patch.object(api, "_request_data", return_value={"id": 1}) as query:
                    api.get_data("exerciseinfo/1/")
                    api.get_data("exerciseinfo/1/")
                    self.assertEqual(query.call_count, 1)
                    api.get_data("exerciseinfo/1/", refresh=True)
                    self.assertEqual(query.call_count, 2)
        response = requests.Response()
        response.status_code = 200
        response._content = b"<html>not JSON</html>"
        with patch.object(api.requests, "get", return_value=response):
            with self.assertRaisesRegex(RuntimeError, "Invalid JSON response"):
                api._request_data(api.BASE_URL + "exerciseinfo/", None)


if __name__ == "__main__":
    unittest.main()

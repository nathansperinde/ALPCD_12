"""Testes das bases: HTTP real contra um servidor local e ficheiros temporários."""

import csv
import io
import json
import tempfile
import threading
import time
import unittest
from contextlib import redirect_stdout
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from typer.testing import CliRunner

from fitcli import app
from fitlib import api, exercises, output


class Handler(BaseHTTPRequestHandler):
    calls = []

    def log_message(self, *args):
        pass

    def do_GET(self):
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        self.calls.append((parsed.path, query, dict(self.headers)))
        status, data = 200, {"id": 1}
        if parsed.path.endswith("/pages/"):
            if query.get("offset") == ["1"]:
                data = {"results": [{"id": 2}], "next": None}
            else:
                data = {"results": [{"id": 1}], "next": "pages/?offset=1&language=2"}
        elif parsed.path.endswith("/empty/"):
            data = {"results": [], "next": None}
        elif parsed.path.endswith("/cycle/"):
            data = {"results": [], "next": "cycle/"}
        elif parsed.path.endswith("/bad-results/"):
            data = {"results": "invalid", "next": None}
        elif parsed.path.endswith("/foreign-next/"):
            data = {"results": [], "next": "https://example.com/api/v2/"}
        elif parsed.path.endswith("/list/"):
            data = []
        elif parsed.path.endswith("/404/"):
            status = 404
        elif parsed.path.endswith("/500/"):
            status = 500
        elif parsed.path.endswith("/slow/"):
            time.sleep(0.1)
        body = b"<html>not JSON</html>" if parsed.path.endswith("/html/") else json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        try:
            self.wfile.write(body)
        except BrokenPipeError:
            pass


class APITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}/api/v2/"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def setUp(self):
        Handler.calls.clear()
        self.base_patch = patch.object(api, "BASE_URL", self.base)
        self.base_patch.start()
        self.addCleanup(self.base_patch.stop)
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        cache_patch = patch.object(api, "CACHE_FILE", Path(directory.name) / "cache.json")
        cache_patch.start()
        self.addCleanup(cache_patch.stop)

    def test_detail_filters_and_headers(self):
        params = {"language": exercises.LANGUAGE}
        self.assertEqual(api.get_data("detail/", params), {"id": 1})
        self.assertEqual(params, {"language": 2})
        path, query, headers = Handler.calls[0]
        self.assertEqual(path, "/api/v2/detail/")
        self.assertEqual(query, {"language": ["2"]})
        self.assertEqual(headers["User-Agent"], "ALPCD-Grupo12/0.1")
        self.assertEqual(headers["Accept"], "application/json")

    def test_pagination_preserves_next_query_without_repeating_filters(self):
        params = {"language": 2, "limit": 1}
        self.assertEqual(api.get_list("pages/", params), [{"id": 1}, {"id": 2}])
        self.assertEqual(len(Handler.calls), 2)
        self.assertEqual(Handler.calls[1][1], {"offset": ["1"], "language": ["2"]})
        self.assertEqual(params, {"language": 2, "limit": 1})

    def test_empty_page(self):
        self.assertEqual(api.get_list("empty/"), [])

    def test_http_errors(self):
        for status in (404, 500):
            with self.subTest(status=status), self.assertRaisesRegex(RuntimeError, f"HTTP {status}"):
                api.get_data(f"{status}/")

    def test_invalid_json_and_top_level(self):
        for endpoint in ("html/", "list/"):
            with self.subTest(endpoint=endpoint), self.assertRaises(RuntimeError):
                api.get_data(endpoint)

    def test_invalid_pages_and_cycles(self):
        for endpoint in ("bad-results/", "cycle/"):
            with self.subTest(endpoint=endpoint), self.assertRaises(RuntimeError):
                api.get_list(endpoint)
        with self.assertRaises(ValueError):
            api.get_list("foreign-next/")

    def test_foreign_url_rejected_before_request(self):
        with self.assertRaises(ValueError):
            api.get_data("https://example.com/api/v2/")
        self.assertEqual(Handler.calls, [])

    def test_timeout(self):
        with patch.object(api.requests, "get", side_effect=api.requests.Timeout) as request:
            with self.assertRaisesRegex(RuntimeError, "timed out"):
                api.get_data("detail/")
            self.assertEqual(request.call_args.kwargs["timeout"], 15)

    def test_connection_error(self):
        with patch.object(api.requests, "get", side_effect=api.requests.ConnectionError):
            with self.assertRaisesRegex(RuntimeError, "Connection error"):
                api.get_data("detail/")


class OutputTests(unittest.TestCase):
    def test_json_keeps_accents_and_is_valid(self):
        data = {"ação": ["halteres", 2]}
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            output.print_json(data)
        self.assertEqual(json.loads(stdout.getvalue()), data)
        self.assertIn("ação", stdout.getvalue())
        self.assertTrue(stdout.getvalue().endswith("\n"))

    def test_csv_preserves_targets_quotes_and_structures(self):
        workout = {"peito": [{"id": 1, "name": 'Supino, "inclinado"\ncom halteres',
                   "category": "Peito", "equipment": ["dumbbell"], "type": "compound"}],
                   "costas": [{"id": 2, "name": "Remada", "extra": True}]}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "treino.csv"
            output.write_workout_csv(workout, path)
            with path.open(encoding="utf-8", newline="") as file:
                reader = csv.DictReader(file)
                rows = list(reader)
                self.assertEqual(reader.fieldnames, list(output.CSV_FIELDS))
            self.assertEqual([row["target"] for row in rows], ["peito", "costas"])
            self.assertEqual(rows[0]["name"], workout["peito"][0]["name"])
            self.assertEqual(json.loads(rows[0]["equipment"]), ["dumbbell"])
            self.assertEqual(rows[1]["equipment"], "")

    def test_empty_csv_has_header_and_replaces_previous_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "treino.csv"
            path.write_text("old content")
            output.write_workout_csv({}, path)
            self.assertEqual(path.read_text().strip(), ",".join(output.CSV_FIELDS))

    def test_cli_reports_api_and_file_errors_without_traceback(self):
        for error in (RuntimeError("Falha HTTP"), OSError("Sem permissão")):
            with self.subTest(error=error), patch("fitcli.exercises.top_exercises", side_effect=error):
                result = CliRunner().invoke(app, ["top", "1"])
                self.assertEqual(result.exit_code, 1)
                self.assertIn(f"Erro: {error}", result.output)
                self.assertNotIn("Traceback", result.output)


if __name__ == "__main__":
    unittest.main()

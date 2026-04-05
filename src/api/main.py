from __future__ import annotations

import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import argparse
import json
from http import HTTPStatus
from typing import Any, Callable
from wsgiref.simple_server import WSGIServer, make_server

from application.catalog import ExperimentalCatalogApplicationService
from application.run_lab import RunLabApplicationService
from api.routes.catalog import (
    build_catalog_category_response,
    build_catalog_response,
)
from api.routes.run_lab import (
    build_run_lab_bootstrap_response,
    build_run_lab_save_and_execute_response,
    build_run_lab_save_config_response,
)


StartResponse = Callable[[str, list[tuple[str, str]]], Any]
Environ = dict[str, Any]


class CatalogApiApp:
    """Minimal WSGI app for the experimental catalog HTTP surface.

    Transitional note:
    - This standard-library WSGI app is a conservative bridge toward a future
      HTTP layer.
    - It is intentionally small and should not be mistaken for the long-term
      product/API architecture.
    """

    def __init__(
        self,
        *,
        catalog_service: ExperimentalCatalogApplicationService | None = None,
        run_lab_service: RunLabApplicationService | None = None,
    ) -> None:
        self.catalog_service = catalog_service or ExperimentalCatalogApplicationService()
        self.run_lab_service = run_lab_service or RunLabApplicationService()

    def __call__(self, environ: Environ, start_response: StartResponse) -> list[bytes]:
        method = environ.get("REQUEST_METHOD", "GET").upper()
        path = environ.get("PATH_INFO", "/")

        try:
            request_body = self._read_json_body(environ)
            status_code, payload = self._dispatch(
                method=method,
                path=path,
                request_body=request_body,
            )
        except json.JSONDecodeError:
            status_code, payload = (
                HTTPStatus.BAD_REQUEST,
                {
                    "error": "invalid_json_body",
                    "message": "Request body must be valid JSON.",
                },
            )
        body = json.dumps(payload, sort_keys=True).encode("utf-8")
        start_response(
            f"{status_code} {HTTPStatus(status_code).phrase}",
            [
                ("Content-Type", "application/json; charset=utf-8"),
                ("Content-Length", str(len(body))),
            ],
        )
        return [body]

    def _dispatch(
        self,
        *,
        method: str,
        path: str,
        request_body: dict[str, Any] | None,
    ) -> tuple[int, dict[str, Any]]:
        if method not in {"GET", "POST"}:
            return HTTPStatus.METHOD_NOT_ALLOWED, {
                "error": "method_not_allowed",
                "message": f"Unsupported method: {method}",
            }

        normalized_path = path.rstrip("/") or "/"
        if normalized_path == "/health":
            if method != "GET":
                return HTTPStatus.METHOD_NOT_ALLOWED, {
                    "error": "method_not_allowed",
                    "message": f"Unsupported method: {method}",
                }
            return HTTPStatus.OK, {"status": "ok"}
        if normalized_path == "/catalog":
            if method != "GET":
                return HTTPStatus.METHOD_NOT_ALLOWED, {
                    "error": "method_not_allowed",
                    "message": f"Unsupported method: {method}",
                }
            return build_catalog_response(self.catalog_service)
        if normalized_path.startswith("/catalog/"):
            if method != "GET":
                return HTTPStatus.METHOD_NOT_ALLOWED, {
                    "error": "method_not_allowed",
                    "message": f"Unsupported method: {method}",
                }
            category = normalized_path.removeprefix("/catalog/")
            return build_catalog_category_response(self.catalog_service, category)
        if normalized_path == "/run-lab":
            if method != "GET":
                return HTTPStatus.METHOD_NOT_ALLOWED, {
                    "error": "method_not_allowed",
                    "message": f"Unsupported method: {method}",
                }
            return build_run_lab_bootstrap_response(self.run_lab_service)
        if normalized_path == "/run-lab/configs":
            if method != "POST":
                return HTTPStatus.METHOD_NOT_ALLOWED, {
                    "error": "method_not_allowed",
                    "message": f"Unsupported method: {method}",
                }
            if request_body is None:
                return HTTPStatus.BAD_REQUEST, {
                    "error": "invalid_json_body",
                    "message": "Expected a JSON request body.",
                }
            return build_run_lab_save_config_response(self.run_lab_service, request_body)
        if normalized_path == "/run-lab/executions":
            if method != "POST":
                return HTTPStatus.METHOD_NOT_ALLOWED, {
                    "error": "method_not_allowed",
                    "message": f"Unsupported method: {method}",
                }
            if request_body is None:
                return HTTPStatus.BAD_REQUEST, {
                    "error": "invalid_json_body",
                    "message": "Expected a JSON request body.",
                }
            return build_run_lab_save_and_execute_response(
                self.run_lab_service,
                request_body,
            )
        return HTTPStatus.NOT_FOUND, {
            "error": "not_found",
            "message": f"Unknown path: {path}",
        }

    def _read_json_body(self, environ: Environ) -> dict[str, Any] | None:
        content_length = environ.get("CONTENT_LENGTH")
        if content_length in {None, "", "0", 0}:
            return None
        try:
            body_size = int(content_length)
        except (TypeError, ValueError):
            return None
        body_stream = environ.get("wsgi.input")
        if body_stream is None:
            return None
        raw_body = body_stream.read(body_size)
        if not raw_body:
            return None
        return json.loads(raw_body.decode("utf-8"))


def create_app(
    *,
    catalog_service: ExperimentalCatalogApplicationService | None = None,
    run_lab_service: RunLabApplicationService | None = None,
) -> CatalogApiApp:
    return CatalogApiApp(
        catalog_service=catalog_service,
        run_lab_service=run_lab_service,
    )


app = create_app()


def create_dev_server(
    *,
    host: str = "127.0.0.1",
    port: int = 8000,
) -> WSGIServer:
    """Create the local development server for the transitional catalog API."""
    return make_server(host, port, app)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the minimal catalog HTTP API for local development."
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    with create_dev_server(host=args.host, port=args.port) as server:
        print(f"Serving catalog API on http://{args.host}:{args.port}")
        server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

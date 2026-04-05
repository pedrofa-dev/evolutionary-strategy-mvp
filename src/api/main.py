from __future__ import annotations

import json
from http import HTTPStatus
from typing import Any, Callable

from application.catalog import ExperimentalCatalogApplicationService
from api.routes.catalog import (
    build_catalog_category_response,
    build_catalog_response,
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
    ) -> None:
        self.catalog_service = catalog_service or ExperimentalCatalogApplicationService()

    def __call__(self, environ: Environ, start_response: StartResponse) -> list[bytes]:
        method = environ.get("REQUEST_METHOD", "GET").upper()
        path = environ.get("PATH_INFO", "/")

        status_code, payload = self._dispatch(method=method, path=path)
        body = json.dumps(payload, sort_keys=True).encode("utf-8")
        start_response(
            f"{status_code} {HTTPStatus(status_code).phrase}",
            [
                ("Content-Type", "application/json; charset=utf-8"),
                ("Content-Length", str(len(body))),
            ],
        )
        return [body]

    def _dispatch(self, *, method: str, path: str) -> tuple[int, dict[str, Any]]:
        if method != "GET":
            return HTTPStatus.METHOD_NOT_ALLOWED, {
                "error": "method_not_allowed",
                "message": f"Unsupported method: {method}",
            }

        normalized_path = path.rstrip("/") or "/"
        if normalized_path == "/health":
            return HTTPStatus.OK, {"status": "ok"}
        if normalized_path == "/catalog":
            return build_catalog_response(self.catalog_service)
        if normalized_path.startswith("/catalog/"):
            category = normalized_path.removeprefix("/catalog/")
            return build_catalog_category_response(self.catalog_service, category)
        return HTTPStatus.NOT_FOUND, {
            "error": "not_found",
            "message": f"Unknown path: {path}",
        }


def create_app() -> CatalogApiApp:
    return CatalogApiApp()


app = create_app()

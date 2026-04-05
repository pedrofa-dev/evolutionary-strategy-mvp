from __future__ import annotations

import json
from wsgiref.util import setup_testing_defaults

from api.main import create_app


def _request(method: str, path: str) -> tuple[int, dict]:
    app = create_app()
    environ: dict[str, object] = {}
    setup_testing_defaults(environ)
    environ["REQUEST_METHOD"] = method
    environ["PATH_INFO"] = path

    captured: dict[str, object] = {}

    def start_response(status: str, headers: list[tuple[str, str]]) -> None:
        captured["status"] = status
        captured["headers"] = headers

    body = b"".join(app(environ, start_response))
    status_code = int(str(captured["status"]).split()[0])
    return status_code, json.loads(body.decode("utf-8"))


def test_health_endpoint_returns_ok() -> None:
    status_code, payload = _request("GET", "/health")

    assert status_code == 200
    assert payload == {"status": "ok"}


def test_catalog_endpoint_returns_application_catalog_payload() -> None:
    status_code, payload = _request("GET", "/catalog")

    assert status_code == 200
    assert "signal_packs" in payload
    assert "experiment_presets" in payload
    assert any(item["id"] == "btc_1h_probe_v1" for item in payload["experiment_presets"])


def test_catalog_category_endpoint_returns_requested_category_only() -> None:
    status_code, payload = _request("GET", "/catalog/signal_packs")

    assert status_code == 200
    assert payload["category"] == "signal_packs"
    assert any(item["id"] == "core_policy_v21_signals_v1" for item in payload["items"])


def test_catalog_category_endpoint_returns_404_for_unknown_category() -> None:
    status_code, payload = _request("GET", "/catalog/unknown")

    assert status_code == 404
    assert payload["error"] == "unknown_catalog_category"


def test_api_rejects_non_get_methods() -> None:
    status_code, payload = _request("POST", "/catalog")

    assert status_code == 405
    assert payload["error"] == "method_not_allowed"

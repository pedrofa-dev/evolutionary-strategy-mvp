from __future__ import annotations

from http import HTTPStatus
from typing import Any

from application.configs import RunConfigBrowserApplicationService


def build_config_list_response(
    service: RunConfigBrowserApplicationService,
) -> tuple[int, dict[str, Any]]:
    return HTTPStatus.OK, {
        "items": [item.to_dict() for item in service.list_configs()]
    }


def build_config_detail_response(
    service: RunConfigBrowserApplicationService,
    config_name: str,
) -> tuple[int, dict[str, Any]]:
    try:
        result = service.get_config(config_name)
    except ValueError as exc:
        return HTTPStatus.NOT_FOUND, {
            "error": "unknown_config",
            "message": str(exc),
        }
    return HTTPStatus.OK, result.to_dict()


def build_config_duplicate_response(
    service: RunConfigBrowserApplicationService,
    payload: dict[str, Any],
) -> tuple[int, dict[str, Any]]:
    try:
        result = service.duplicate_config(
            source_config_name=str(payload["source_config_name"]),
            new_config_name=str(payload["new_config_name"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        return HTTPStatus.BAD_REQUEST, {
            "error": "invalid_config_request",
            "message": str(exc),
        }
    return HTTPStatus.OK, result.to_dict()


def build_config_rename_response(
    service: RunConfigBrowserApplicationService,
    payload: dict[str, Any],
) -> tuple[int, dict[str, Any]]:
    try:
        result = service.rename_config(
            source_config_name=str(payload["source_config_name"]),
            new_config_name=str(payload["new_config_name"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        return HTTPStatus.BAD_REQUEST, {
            "error": "invalid_config_request",
            "message": str(exc),
        }
    return HTTPStatus.OK, result.to_dict()


def build_config_save_response(
    service: RunConfigBrowserApplicationService,
    payload: dict[str, Any],
) -> tuple[int, dict[str, Any]]:
    try:
        result = service.save_config(
            source_config_name=str(payload["source_config_name"]),
            config_payload=dict(payload["config"]),
        )
    except ValueError as exc:
        error_code = "unknown_config" if "Unknown run config" in str(exc) else "invalid_config_request"
        status = HTTPStatus.NOT_FOUND if error_code == "unknown_config" else HTTPStatus.BAD_REQUEST
        return status, {
            "error": error_code,
            "message": str(exc),
        }
    except (KeyError, TypeError) as exc:
        return HTTPStatus.BAD_REQUEST, {
            "error": "invalid_config_request",
            "message": str(exc),
        }
    return HTTPStatus.OK, result.to_dict()


def build_config_save_as_new_response(
    service: RunConfigBrowserApplicationService,
    payload: dict[str, Any],
) -> tuple[int, dict[str, Any]]:
    try:
        result = service.save_config_as_new(
            config_payload=dict(payload["config"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        return HTTPStatus.BAD_REQUEST, {
            "error": "invalid_config_request",
            "message": str(exc),
        }
    return HTTPStatus.OK, result.to_dict()

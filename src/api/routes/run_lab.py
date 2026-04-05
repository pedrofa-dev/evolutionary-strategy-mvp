from __future__ import annotations

from http import HTTPStatus
from typing import Any

from application.run_lab import RunLabApplicationService


def build_run_lab_bootstrap_response(
    service: RunLabApplicationService,
) -> tuple[int, dict[str, Any]]:
    return HTTPStatus.OK, service.get_bootstrap().to_dict()


def build_run_lab_save_config_response(
    service: RunLabApplicationService,
    payload: dict[str, Any],
) -> tuple[int, dict[str, Any]]:
    try:
        result = service.save_run_config(payload)
    except (KeyError, TypeError, ValueError) as exc:
        return (
            HTTPStatus.BAD_REQUEST,
            {
                "error": "invalid_run_lab_request",
                "message": str(exc),
            },
        )
    return HTTPStatus.OK, result.to_dict()


def build_run_lab_save_and_execute_response(
    service: RunLabApplicationService,
    payload: dict[str, Any],
) -> tuple[int, dict[str, Any]]:
    try:
        result = service.save_and_execute(payload)
    except (KeyError, TypeError, ValueError) as exc:
        return (
            HTTPStatus.BAD_REQUEST,
            {
                "error": "invalid_run_lab_request",
                "message": str(exc),
            },
        )
    return HTTPStatus.OK, result.to_dict()

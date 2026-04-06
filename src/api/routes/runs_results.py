from __future__ import annotations

from http import HTTPStatus
from typing import Any

from application.runs_results import RunsResultsApplicationService


def build_campaigns_response(
    service: RunsResultsApplicationService,
) -> tuple[int, dict[str, Any]]:
    return HTTPStatus.OK, {
        "campaigns": [campaign.to_dict() for campaign in service.list_campaigns()]
    }


def build_campaign_detail_response(
    service: RunsResultsApplicationService,
    campaign_id: str,
) -> tuple[int, dict[str, Any]]:
    campaign = service.get_campaign(campaign_id)
    if campaign is None:
        return HTTPStatus.NOT_FOUND, {
            "error": "unknown_campaign",
            "message": f"Unknown campaign: {campaign_id}",
        }
    return HTTPStatus.OK, campaign.to_dict()


def build_campaign_compare_response(
    service: RunsResultsApplicationService,
    campaign_ids: list[str],
) -> tuple[int, dict[str, Any]]:
    if not campaign_ids:
        return HTTPStatus.BAD_REQUEST, {
            "error": "missing_campaign_ids",
            "message": "At least one campaign id is required.",
        }

    comparisons = service.compare_campaigns(campaign_ids)
    return HTTPStatus.OK, {
        "items": [item.to_dict() for item in comparisons],
    }


def build_execution_monitor_response(
    service: RunsResultsApplicationService,
) -> tuple[int, dict[str, Any]]:
    return HTTPStatus.OK, {
        "items": [item.to_dict() for item in service.list_execution_monitor_items()]
    }


def build_delete_campaign_response(
    service: RunsResultsApplicationService,
    campaign_id: str,
) -> tuple[int, dict[str, Any]]:
    try:
        result = service.delete_campaign(campaign_id)
    except ValueError as exc:
        return HTTPStatus.BAD_REQUEST, {
            "error": "campaign_delete_blocked",
            "message": str(exc),
        }

    if result is None:
        return HTTPStatus.NOT_FOUND, {
            "error": "unknown_campaign",
            "message": f"Unknown campaign: {campaign_id}",
        }

    return HTTPStatus.OK, result.to_dict()


def build_cancel_queue_job_response(
    service: RunsResultsApplicationService,
    job_id: str,
) -> tuple[int, dict[str, Any]]:
    try:
        result = service.cancel_queued_job(job_id)
    except ValueError as exc:
        return HTTPStatus.BAD_REQUEST, {
            "error": "queue_job_cancel_blocked",
            "message": str(exc),
        }

    if result is None:
        return HTTPStatus.NOT_FOUND, {
            "error": "unknown_queue_job",
            "message": f"Unknown queue job: {job_id}",
        }

    return HTTPStatus.OK, result.to_dict()

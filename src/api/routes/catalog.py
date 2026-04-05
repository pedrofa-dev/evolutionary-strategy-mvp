from __future__ import annotations

from http import HTTPStatus
from typing import Any

from application.catalog import ExperimentalCatalogApplicationService


CATALOG_CATEGORIES = (
    "signal_plugins",
    "policy_engines",
    "gene_type_definitions",
    "signal_packs",
    "genome_schemas",
    "decision_policies",
    "mutation_profiles",
    "experiment_presets",
)


def build_catalog_response(
    service: ExperimentalCatalogApplicationService,
) -> tuple[int, dict[str, Any]]:
    """Build the top-level catalog response for the transitional HTTP layer."""
    return HTTPStatus.OK, service.get_catalog_payload()


def build_catalog_category_response(
    service: ExperimentalCatalogApplicationService,
    category: str,
) -> tuple[int, dict[str, Any]]:
    """Build one category response for the transitional HTTP layer."""
    if category not in CATALOG_CATEGORIES:
        return (
            HTTPStatus.NOT_FOUND,
            {
                "error": "unknown_catalog_category",
                "message": f"Unknown catalog category: {category}",
            },
        )

    return (
        HTTPStatus.OK,
        {
            "category": category,
            "items": service.get_catalog_category_payload(category),
        },
    )

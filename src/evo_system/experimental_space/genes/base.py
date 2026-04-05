from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class GeneTypePlugin(Protocol):
    """Minimal future plugin seam for contributed gene-type definitions.

    Why it is intentionally small:
    - The current runtime already has a canonical ``GeneTypeCatalog`` and
      ``GenomeSchema`` flow.
    - This base only marks the extension point for future plugin registration;
      it does not migrate or replace the active catalog behavior yet.
    """

    name: str

    def build_gene_type_definitions(self) -> dict[str, Any]:
        """Return contributed gene-type definitions keyed by stable name."""

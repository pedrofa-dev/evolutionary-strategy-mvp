from evo_system.experimental_space import get_default_genome_schema
from evo_system.experimental_space.gene_catalog import (
    MODULAR_GENOME_V1_GENE_TYPE_CATALOG,
    GeneTypeDefinition,
    GenomeSchemaSlot,
    StructuralCompatibility,
)


def test_gene_catalog_exposes_serializable_gene_type_definitions() -> None:
    definitions = MODULAR_GENOME_V1_GENE_TYPE_CATALOG.describe_gene_types()

    assert [definition.name for definition in definitions] == [
        "entry_context",
        "entry_trigger",
        "exit_policy",
        "trade_control",
    ]
    assert isinstance(definitions[0], GeneTypeDefinition)
    assert definitions[0].to_dict()["field_specs"][0]["field_name"] == "min_trend_strength"
    assert definitions[1].supports_constraints is True


def test_gene_catalog_exposes_serializable_schema_slots() -> None:
    slots = MODULAR_GENOME_V1_GENE_TYPE_CATALOG.describe_schema_slots()

    assert isinstance(slots[0], GenomeSchemaSlot)
    assert [slot.name for slot in slots] == [
        "entry_context",
        "entry_trigger",
        "exit_policy",
        "trade_control",
    ]
    assert slots[2].slot_kind == "gene_block"
    assert "stop_loss_pct" in slots[2].field_names
    assert slots[0].required is True
    assert slots[0].cardinality_min == 1
    assert slots[0].cardinality_max == 1


def test_gene_catalog_structural_compatibility_matches_default_schema() -> None:
    schema = get_default_genome_schema()
    compatibility = schema.get_gene_type_catalog().describe_structural_compatibility(
        schema_name=schema.name
    )

    assert isinstance(compatibility, StructuralCompatibility)
    assert compatibility.schema_name == "policy_v2_default"
    assert compatibility.gene_catalog_name == "modular_genome_v1_gene_catalog"
    assert compatibility.module_names == (
        "entry_context",
        "entry_trigger",
        "exit_policy",
        "trade_control",
    )
    assert compatibility.policy_v2_enabled_required is True


def test_gene_catalog_to_dict_exposes_structural_metadata_only() -> None:
    payload = MODULAR_GENOME_V1_GENE_TYPE_CATALOG.to_dict()

    assert payload["name"] == "modular_genome_v1_gene_catalog"
    assert payload["gene_types"][0]["name"] == "entry_context"
    assert payload["schema_slots"][0]["name"] == "entry_context"
    assert payload["schema_slots"][0]["required"] is True
    assert payload["schema_slots"][0]["cardinality_min"] == 1
    assert payload["schema_slots"][0]["cardinality_max"] == 1
    assert payload["schema_fields"][0]["field_name"] == "trend_window"


def test_gene_type_definitions_and_schema_slots_are_derived_structural_views() -> None:
    definition = MODULAR_GENOME_V1_GENE_TYPE_CATALOG.describe_gene_types()[0]
    slot = MODULAR_GENOME_V1_GENE_TYPE_CATALOG.describe_schema_slots()[0]

    assert definition.builder_name == "from_dict"
    assert definition.to_dict()["supports_constraints"] is False
    assert slot.to_dict()["slot_kind"] == "gene_block"

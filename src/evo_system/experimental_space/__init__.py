from evo_system.experimental_space.base import (
    DecisionPolicy,
    GenomeSchema,
    MarketMode,
    MutationProfileDefinition,
    SignalPack,
)

__all__ = [
    "DecisionPolicy",
    "GenomeSchema",
    "MarketMode",
    "MutationProfileDefinition",
    "SignalPack",
    "decision_policy_registry",
    "genome_schema_registry",
    "get_default_market_mode",
    "build_runtime_component_fingerprint",
    "get_default_decision_policy",
    "get_default_genome_schema",
    "get_default_mutation_profile_definition",
    "get_default_signal_pack",
    "get_decision_policy",
    "get_genome_schema",
    "get_market_mode",
    "get_mutation_profile_definition",
    "get_signal_pack",
    "market_mode_registry",
    "mutation_profile_registry",
    "signal_pack_registry",
]


def __getattr__(name: str):
    if name in {
        "build_runtime_component_fingerprint",
        "decision_policy_registry",
        "genome_schema_registry",
        "get_default_market_mode",
        "get_default_decision_policy",
        "get_default_genome_schema",
        "get_default_mutation_profile_definition",
        "get_default_signal_pack",
        "get_decision_policy",
        "get_genome_schema",
        "get_market_mode",
        "get_mutation_profile_definition",
        "get_signal_pack",
        "market_mode_registry",
        "mutation_profile_registry",
        "signal_pack_registry",
    }:
        if name == "build_runtime_component_fingerprint":
            from evo_system.experimental_space import identity

            return getattr(identity, name)

        from evo_system.experimental_space import defaults

        return getattr(defaults, name)

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

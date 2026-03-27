from evo_system.domain.genome import Genome
from evo_system.mutation.mutator import MutationProfile, Mutator


def test_mutator_uses_default_mutation_profile_when_not_provided() -> None:
    mutator = Mutator(seed=42)

    assert mutator.profile == MutationProfile()


def test_mutator_accepts_custom_mutation_profile() -> None:
    profile = MutationProfile(
        strong_mutation_probability=0.25,
        numeric_delta_scale=1.5,
        flag_flip_probability=0.10,
        weight_delta=0.35,
        window_step_mode="wide",
    )

    mutator = Mutator(seed=42, profile=profile)

    assert mutator.profile == profile


def test_mutate_returns_new_genome() -> None:
    genome = Genome(
        threshold_open=0.8,
        threshold_close=0.4,
        position_size=0.2,
        stop_loss=0.05,
        take_profit=0.1,
    )

    mutator = Mutator(seed=42)

    mutated = mutator.mutate(genome)

    assert mutated is not genome
    assert isinstance(mutated, Genome)


def test_mutate_is_reproducible_with_same_seed() -> None:
    genome = Genome(
        threshold_open=0.8,
        threshold_close=0.4,
        position_size=0.2,
        stop_loss=0.05,
        take_profit=0.1,
    )

    mutator1 = Mutator(seed=42)
    mutator2 = Mutator(seed=42)

    mutated1 = mutator1.mutate(genome)
    mutated2 = mutator2.mutate(genome)

    assert mutated1 == mutated2


def test_mutate_preserves_valid_ranges() -> None:
    genome = Genome(
        threshold_open=0.8,
        threshold_close=0.4,
        position_size=0.2,
        stop_loss=0.05,
        take_profit=0.1,
    )

    mutator = Mutator(seed=42)

    mutated = mutator.mutate(genome)

    mutated.validate()


def test_mutate_preserves_threshold_order() -> None:
    genome = Genome(
        threshold_open=0.6,
        threshold_close=0.2,
        position_size=0.1,
        stop_loss=0.03,
        take_profit=0.08,
    )

    mutator = Mutator(seed=1)

    mutated = mutator.mutate(genome)

    assert mutated.threshold_close <= mutated.threshold_open


def test_mutate_can_produce_valid_mutations_repeatedly() -> None:
    genome = Genome(
        threshold_open=0.7,
        threshold_close=0.3,
        position_size=0.15,
        stop_loss=0.03,
        take_profit=0.09,
        use_trend=True,
        trend_threshold=0.0006,
        trend_window=4,
        use_exit_momentum=True,
        exit_momentum_threshold=-0.0008,
    )

    mutator = Mutator(seed=123)

    for _ in range(50):
        mutated = mutator.mutate(genome)
        mutated.validate()


def test_mutate_updates_new_feature_weights_with_small_mutation() -> None:
    genome = Genome(
        threshold_open=0.8,
        threshold_close=0.4,
        position_size=0.2,
        stop_loss=0.05,
        take_profit=0.1,
        weight_trend_strength=0.2,
        weight_realized_volatility=-0.3,
        weight_trend_long=0.4,
        weight_breakout=-0.2,
    )

    profile = MutationProfile(strong_mutation_probability=0.0)
    mutator = Mutator(seed=42, profile=profile)

    mutated = mutator.mutate(genome)

    assert mutated.weight_trend_strength != genome.weight_trend_strength
    assert mutated.weight_realized_volatility != genome.weight_realized_volatility
    assert mutated.weight_trend_long != genome.weight_trend_long
    assert mutated.weight_breakout != genome.weight_breakout


def test_strong_mutate_sets_new_feature_weights_in_valid_range() -> None:
    genome = Genome(
        threshold_open=0.8,
        threshold_close=0.4,
        position_size=0.2,
        stop_loss=0.05,
        take_profit=0.1,
    )

    profile = MutationProfile(strong_mutation_probability=1.0)
    mutator = Mutator(seed=7, profile=profile)

    mutated = mutator.mutate(genome)

    assert -2.0 <= mutated.weight_trend_strength <= 2.0
    assert -2.0 <= mutated.weight_realized_volatility <= 2.0
    assert -2.0 <= mutated.weight_trend_long <= 2.0
    assert -2.0 <= mutated.weight_breakout <= 2.0

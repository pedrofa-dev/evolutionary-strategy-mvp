from evo_system.domain.genome import Genome
from evo_system.mutation.mutator import Mutator


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
        use_momentum=True,
        momentum_threshold=0.0008,
        use_exit_momentum=True,
        exit_momentum_threshold=-0.0008,
    )

    mutator_1 = Mutator(seed=42)
    mutator_2 = Mutator(seed=42)

    mutated_1 = mutator_1.mutate(genome)
    mutated_2 = mutator_2.mutate(genome)

    assert mutated_1 == mutated_2


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
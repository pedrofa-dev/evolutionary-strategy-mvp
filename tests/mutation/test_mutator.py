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
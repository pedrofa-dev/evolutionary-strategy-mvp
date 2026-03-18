from evo_system.domain.run_record import RunRecord


def test_run_record_to_dict_returns_serializable_data() -> None:
    record = RunRecord(
        run_id="run-001",
        mutation_seed=42,
        population_size=4,
        target_population_size=4,
        survivors_count=2,
        generations_planned=5,
    )

    data = record.to_dict()

    assert data == {
        "run_id": "run-001",
        "mutation_seed": 42,
        "population_size": 4,
        "target_population_size": 4,
        "survivors_count": 2,
        "generations_planned": 5,
    }
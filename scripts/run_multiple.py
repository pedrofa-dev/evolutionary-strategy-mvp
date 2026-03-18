import uuid
from pathlib import Path

from evo_system.domain.agent import Agent
from evo_system.domain.genome import Genome
from evo_system.domain.run_record import RunRecord
from evo_system.orchestration.config_loader import load_run_config
from evo_system.orchestration.runner import EvolutionRunner
from evo_system.storage.sqlite_store import SQLiteStore


CONFIGS_DIR = Path("configs/runs")


def build_initial_population(population_size: int) -> list[Agent]:
    base_genomes = [
        Genome(0.8, 0.4, 0.2, 0.05, 0.1),
        Genome(0.7, 0.3, 0.3, 0.04, 0.15),
        Genome(0.6, 0.2, 0.1, 0.03, 0.08),
        Genome(0.9, 0.5, 0.25, 0.06, 0.12),
    ]

    if population_size > len(base_genomes):
        raise ValueError(
            f"population_size cannot be greater than {len(base_genomes)} "
            "with the current initial population builder"
        )

    selected_genomes = base_genomes[:population_size]
    return [Agent.create(genome) for genome in selected_genomes]


def execute_run(config_path: Path, store: SQLiteStore) -> None:
    config = load_run_config(str(config_path))
    run_id = str(uuid.uuid4())

    runner = EvolutionRunner(mutation_seed=config.mutation_seed)
    population = build_initial_population(config.population_size)

    run_record = RunRecord(
        run_id=run_id,
        mutation_seed=config.mutation_seed,
        population_size=config.population_size,
        target_population_size=config.target_population_size,
        survivors_count=config.survivors_count,
        generations_planned=config.generations_planned,
    )

    store.save_run_record(run_record)

    print(f"\nConfig: {config_path.name}")
    print(f"Run ID: {run_id}")

    for generation_number in range(1, config.generations_planned + 1):
        evaluated_agents = runner.run_generation(population)

        summary = runner.summarize_generation(
            generation_number=generation_number,
            evaluated_agents=evaluated_agents,
        )

        store.save_generation_result(run_id, summary)

        print(
            f"Generation {summary.generation_number} | "
            f"Best fitness: {summary.best_fitness:.4f} | "
            f"Average fitness: {summary.average_fitness:.4f}"
        )

        if generation_number < config.generations_planned:
            population = runner.build_next_generation(
                evaluated_agents=evaluated_agents,
                survivors_count=config.survivors_count,
                target_population_size=config.target_population_size,
            )


def main() -> None:
    store = SQLiteStore()
    store.initialize()

    config_files = sorted(CONFIGS_DIR.glob("*.json"))

    if not config_files:
        print("No config files found.")
        return

    for config_path in config_files:
        execute_run(config_path, store)


if __name__ == "__main__":
    main()
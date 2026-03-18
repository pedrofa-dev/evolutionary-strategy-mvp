import uuid

from evo_system.domain.agent import Agent
from evo_system.domain.genome import Genome
from evo_system.domain.run_record import RunRecord
from evo_system.orchestration.runner import EvolutionRunner
from evo_system.storage.sqlite_store import SQLiteStore


def build_initial_population() -> list[Agent]:
    genomes = [
        Genome(0.8, 0.4, 0.2, 0.05, 0.1),
        Genome(0.7, 0.3, 0.3, 0.04, 0.15),
        Genome(0.6, 0.2, 0.1, 0.03, 0.08),
        Genome(0.9, 0.5, 0.25, 0.06, 0.12),
    ]

    return [Agent.create(genome) for genome in genomes]


def main() -> None:
    #Run data
    run_id = str(uuid.uuid4())
    mutation_seed = 42
    population = build_initial_population()
    population_size = len(population)
    target_population_size = 4
    survivors_count = 2
    generations_planned = 5

    run_record = RunRecord(
        run_id=run_id,
        mutation_seed=mutation_seed,
        population_size=population_size,
        survivors_count=survivors_count,
        generations_planned=generations_planned,
        target_population_size=target_population_size
    )

    print(f"Run ID: {run_id}")
    runner = EvolutionRunner(mutation_seed)
    store = SQLiteStore()
    store.initialize()
    store.save_run_record(run_record)


    

    for generation_number in range(1, generations_planned + 1):
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

        if generation_number < generations_planned:
            population = runner.build_next_generation(
                evaluated_agents=evaluated_agents,
                survivors_count=survivors_count,
                target_population_size=target_population_size,
            )


if __name__ == "__main__":
    main()
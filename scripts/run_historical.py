import uuid

from evo_system.domain.agent import Agent
from evo_system.domain.genome import Genome
from evo_system.domain.run_record import RunRecord
from evo_system.environment.csv_loader import load_historical_candles
from evo_system.environment.historical_environment import HistoricalEnvironment
from evo_system.orchestration.config_loader import load_run_config
from evo_system.orchestration.runner import EvolutionRunner
from evo_system.storage.sqlite_store import SQLiteStore
from pathlib import Path


DATASET_PATH = Path("data/real/BTCUSDT-1h-2026-02.csv")


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


def main() -> None:
    config = load_run_config("configs/run_config.json")

    candles = load_historical_candles(DATASET_PATH)
    split_index = int(len(candles) * 0.7)

    train_candles = candles[:split_index]
    validation_candles = candles[split_index:]

    if not train_candles or not validation_candles:
        raise ValueError("Dataset split produced an empty train or validation set")

    train_env = HistoricalEnvironment(train_candles)
    validation_env = HistoricalEnvironment(validation_candles)

    run_id = str(uuid.uuid4())

    runner = EvolutionRunner(
        environment=train_env,
        mutation_seed=config.mutation_seed,
    )

    store = SQLiteStore()
    store.initialize()

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

    print(f"Run ID: {run_id}")
    print(f"Dataset: {DATASET_PATH}")
    print(f"Train candles: {len(train_candles)} | Validation candles: {len(validation_candles)}")

    for generation_number in range(1, config.generations_planned + 1):
        evaluated_agents = runner.run_generation(population)

        summary = runner.summarize_generation(
            generation_number=generation_number,
            evaluated_agents=evaluated_agents,
        )


        store.save_generation_result(run_id, summary)

        validation_results = [
            (
                agent,
                runner.fitness_calculator.calculate(
                    validation_env.run_episode(agent)
                ),
            )
            for agent, _ in evaluated_agents
        ]

        best_validation = max(fitness for _, fitness in validation_results)
        average_validation = (
            sum(fitness for _, fitness in validation_results)
            / len(validation_results)
        )
        best_agent, best_fitness = max(
            evaluated_agents,
            key=lambda item: item[1],
        )

        diagnostics = train_env.get_episode_diagnostics(best_agent)

        print(
            f"Generation {summary.generation_number} | "
            f"Train best: {summary.best_fitness:.4f} | "
            f"Train average: {summary.average_fitness:.4f}"
        )
        print(
            f"Validation | "
            f"Best: {best_validation:.4f} | "
            f"Average: {average_validation:.4f}"
        )
        print("Best agent genome:", best_agent.genome)
        print("Best agent fitness:", best_fitness)
        print(
            "Best agent diagnostics | "
            f"Trades: {diagnostics['trades']} | "
            f"Profit: {diagnostics['profit']:.4f} | "
            f"Cost: {diagnostics['cost']:.4f} | "
            f"Stability: {diagnostics['stability']:.4f}"
        )

        if generation_number < config.generations_planned:
            population = runner.build_next_generation(
                evaluated_agents=evaluated_agents,
                survivors_count=config.survivors_count,
                target_population_size=config.target_population_size,
            )


if __name__ == "__main__":
    main()
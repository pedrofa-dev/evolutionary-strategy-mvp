import random
import uuid
from pathlib import Path

from evo_system.domain.agent import Agent
from evo_system.domain.agent_evaluation import AgentEvaluation
from evo_system.domain.genome import Genome
from evo_system.domain.run_record import RunRecord
from evo_system.environment.csv_loader import load_historical_candles
from evo_system.environment.dataset_pool_loader import DatasetPoolLoader
from evo_system.environment.historical_environment import HistoricalEnvironment
from evo_system.orchestration.agent_evaluator import AgentEvaluator
from evo_system.orchestration.config_loader import load_run_config
from evo_system.orchestration.runner import EvolutionRunner
from evo_system.storage.sqlite_store import SQLiteStore


DATA_ROOT = Path("data/real")
TRAIN_SAMPLE_SIZE = 4


def build_initial_population(population_size: int) -> list[Agent]:
    base_genomes = [
        Genome(
            threshold_open=0.8,
            threshold_close=0.4,
            position_size=0.2,
            stop_loss=0.05,
            take_profit=0.1,
            use_momentum=False,
            momentum_threshold=0.0,
            use_trend=False,
            trend_threshold=0.0,
            trend_window=5,
        ),
        Genome(
            threshold_open=0.7,
            threshold_close=0.3,
            position_size=0.3,
            stop_loss=0.04,
            take_profit=0.15,
            use_momentum=True,
            momentum_threshold=0.001,
            use_trend=False,
            trend_threshold=0.0,
            trend_window=5,
        ),
        Genome(
            threshold_open=0.6,
            threshold_close=0.2,
            position_size=0.1,
            stop_loss=0.03,
            take_profit=0.08,
            use_momentum=True,
            momentum_threshold=0.0,
            use_trend=True,
            trend_threshold=0.0,
            trend_window=5,
        ),
        Genome(
            threshold_open=0.9,
            threshold_close=0.5,
            position_size=0.25,
            stop_loss=0.06,
            take_profit=0.12,
            use_momentum=True,
            momentum_threshold=-0.001,
            use_trend=True,
            trend_threshold=0.001,
            trend_window=8,
        ),
    ]

    if population_size > len(base_genomes):
        raise ValueError(
            f"population_size cannot be greater than {len(base_genomes)} "
            "with the current initial population builder"
        )

    selected_genomes = base_genomes[:population_size]
    return [Agent.create(genome) for genome in selected_genomes]


def build_environment(dataset_path: Path) -> HistoricalEnvironment:
    candles = load_historical_candles(dataset_path)
    return HistoricalEnvironment(candles)


def summarize_generation_scores(
    evaluations: list[AgentEvaluation],
) -> tuple[float, float]:
    selection_scores = [evaluation.selection_score for evaluation in evaluations]
    best_score = max(selection_scores)
    average_score = sum(selection_scores) / len(selection_scores)
    return best_score, average_score


def format_dataset_list(paths: list[Path]) -> str:
    return ", ".join(str(path.relative_to(DATA_ROOT)) for path in paths)


def format_evaluation(label: str, evaluation: AgentEvaluation) -> str:
    return (
        f"{label} -> "
        f"valid={evaluation.is_valid} | "
        f"score={evaluation.aggregated_score:.4f} | "
        f"selection={evaluation.selection_score:.4f} | "
        f"dispersion={evaluation.dispersion:.4f} | "
        f"profit={evaluation.median_profit:.4f} | "
        f"drawdown={evaluation.median_drawdown:.4f} | "
        f"trades={evaluation.median_trades:.1f}"
    )


def print_dataset_breakdown(
    paths: list[Path],
    evaluation: AgentEvaluation,
    label: str,
) -> None:
    print(f"{label} breakdown:")
    for path, score, profit, drawdown in zip(
        paths,
        evaluation.dataset_scores,
        evaluation.dataset_profits,
        evaluation.dataset_drawdowns,
    ):
        print(
            f"  {path.relative_to(DATA_ROOT)} -> "
            f"score={score:.4f} | "
            f"profit={profit:.4f} | "
            f"dd={drawdown:.4f}"
        )


def main() -> None:
    config = load_run_config("configs/run_config.json")

    evaluator = AgentEvaluator()
    loader = DatasetPoolLoader()
    train_dataset_paths, validation_dataset_paths = loader.load_paths(DATA_ROOT)

    run_id = str(uuid.uuid4())

    bootstrap_environment = build_environment(train_dataset_paths[0])

    runner = EvolutionRunner(
        environment=bootstrap_environment,
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
    print(
        f"Datasets -> train={len(train_dataset_paths)} | "
        f"validation={len(validation_dataset_paths)}"
    )

    random_generator = random.Random(config.mutation_seed)

    for generation_number in range(1, config.generations_planned + 1):
        sampled_train_paths = random_generator.sample(
            train_dataset_paths,
            k=min(TRAIN_SAMPLE_SIZE, len(train_dataset_paths)),
        )

        train_environments = [build_environment(path) for path in sampled_train_paths]
        validation_environments = [
            build_environment(path) for path in validation_dataset_paths
        ]

        evaluated_agents: list[tuple[Agent, float]] = []
        agent_evaluations: dict[str, AgentEvaluation] = {}

        for agent in population:
            evaluation = evaluator.evaluate(
                agent=agent,
                environments=train_environments,
            )

            evaluated_agents.append((agent, evaluation.selection_score))
            agent_evaluations[agent.id] = evaluation

        summary = runner.summarize_generation(
            generation_number=generation_number,
            evaluated_agents=evaluated_agents,
        )
        store.save_generation_result(run_id, summary)

        best_agent = max(
            population,
            key=lambda agent: (
                agent_evaluations[agent.id].is_valid,
                agent_evaluations[agent.id].selection_score,
            ),
        )
        best_train_evaluation = agent_evaluations[best_agent.id]

        validation_evaluation = evaluator.evaluate(
            agent=best_agent,
            environments=validation_environments,
        )

        train_best, train_average = summarize_generation_scores(
            list(agent_evaluations.values())
        )

        print()
        print(f"Generation {generation_number}")
        print(f"Train sample -> {format_dataset_list(sampled_train_paths)}")
        print(
            f"Selection scores -> best={train_best:.4f} | "
            f"average={train_average:.4f}"
        )
        print(f"Best genome -> {best_agent.genome}")
        print(format_evaluation("Train", best_train_evaluation))
        print(format_evaluation("Validation", validation_evaluation))
        print_dataset_breakdown(sampled_train_paths, best_train_evaluation, "Train")
        print_dataset_breakdown(
            validation_dataset_paths,
            validation_evaluation,
            "Validation",
        )

        if best_train_evaluation.violations:
            print(f"Train violations -> {', '.join(best_train_evaluation.violations)}")

        if validation_evaluation.violations:
            print(
                f"Validation violations -> "
                f"{', '.join(validation_evaluation.violations)}"
            )

        if generation_number < config.generations_planned:
            population = runner.build_next_generation(
                evaluated_agents=evaluated_agents,
                survivors_count=config.survivors_count,
                target_population_size=config.target_population_size,
            )


if __name__ == "__main__":
    main()
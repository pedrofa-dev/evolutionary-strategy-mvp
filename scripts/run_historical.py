import random
import uuid
from pathlib import Path
from dataclasses import dataclass

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
from evo_system.domain.run_summary import HistoricalRunSummary


DATA_ROOT = Path("data/real")
TRAIN_SAMPLE_SIZE = 4
RUN_LOG_DIR = Path("artifacts/runs")


def build_initial_population(population_size: int) -> list[Agent]:
    if population_size <= 0:
        raise ValueError("population_size must be greater than 0")

    random_generator = random.Random(12345)

    base_genomes = [
        Genome(
            threshold_open=0.80,
            threshold_close=0.40,
            position_size=0.20,
            stop_loss=0.05,
            take_profit=0.10,
            use_exit_momentum=True,
            exit_momentum_threshold=-0.0005,
        ),
        Genome(
            threshold_open=0.78,
            threshold_close=0.38,
            position_size=0.18,
            stop_loss=0.05,
            take_profit=0.12,
            use_exit_momentum=True,
            exit_momentum_threshold=-0.0003,
        ),
        Genome(
            threshold_open=0.72,
            threshold_close=0.30,
            position_size=0.16,
            stop_loss=0.04,
            take_profit=0.10,
            use_momentum=True,
            momentum_threshold=0.0008,
            use_exit_momentum=True,
            exit_momentum_threshold=-0.0008,
        ),
        Genome(
            threshold_open=0.70,
            threshold_close=0.28,
            position_size=0.15,
            stop_loss=0.03,
            take_profit=0.09,
            use_trend=True,
            trend_threshold=0.0006,
            trend_window=4,
            use_exit_momentum=True,
            exit_momentum_threshold=-0.0008,
        ),
        Genome(
            threshold_open=0.66,
            threshold_close=0.24,
            position_size=0.10,
            stop_loss=0.02,
            take_profit=0.06,
            use_momentum=True,
            momentum_threshold=0.0005,
            use_trend=True,
            trend_threshold=0.0004,
            trend_window=3,
            use_exit_momentum=True,
            exit_momentum_threshold=-0.0005,
        ),
        Genome(
            threshold_open=0.68,
            threshold_close=0.26,
            position_size=0.08,
            stop_loss=0.025,
            take_profit=0.07,
            use_momentum=True,
            momentum_threshold=0.0012,
            use_trend=True,
            trend_threshold=0.0008,
            trend_window=2,
            use_exit_momentum=True,
            exit_momentum_threshold=-0.0003,
        ),
        Genome(
            threshold_open=0.84,
            threshold_close=0.45,
            position_size=0.22,
            stop_loss=0.06,
            take_profit=0.14,
            use_trend=True,
            trend_threshold=0.0015,
            trend_window=6,
            use_exit_momentum=True,
            exit_momentum_threshold=-0.0006,
        ),
        Genome(
            threshold_open=0.76,
            threshold_close=0.34,
            position_size=0.14,
            stop_loss=0.04,
            take_profit=0.11,
            use_exit_momentum=True,
            exit_momentum_threshold=-0.0010,
        ),
    ]

    genomes = list(base_genomes)

    while len(genomes) < population_size:
        threshold_open = random_generator.uniform(0.45, 0.90)
        threshold_close = random_generator.uniform(0.15, min(0.45, threshold_open))

        use_momentum = random_generator.choice([True, False])
        use_trend = random_generator.choice([True, False])
        use_exit_momentum = random_generator.choice([True, False])

        genome = Genome(
            threshold_open=threshold_open,
            threshold_close=threshold_close,
            position_size=random_generator.uniform(0.05, 0.25),
            stop_loss=random_generator.uniform(0.01, 0.06),
            take_profit=random_generator.uniform(0.03, 0.18),
            use_momentum=use_momentum,
            momentum_threshold=0.0,
            use_trend=use_trend,
            trend_threshold=0.0,
            trend_window=random_generator.randint(2, 8),
            use_exit_momentum=use_exit_momentum,
            exit_momentum_threshold=0.0,
        )

        if use_momentum:
            genome = genome.copy_with(
                momentum_threshold=random_generator.uniform(-0.002, 0.002)
            )

        if use_trend:
            genome = genome.copy_with(
                trend_threshold=random_generator.uniform(-0.002, 0.002)
            )

        if use_exit_momentum:
            genome = genome.copy_with(
                exit_momentum_threshold=random_generator.uniform(-0.002, 0.0)
            )

        genomes.append(genome)

    selected_genomes = genomes[:population_size]
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


def build_dataset_breakdown_lines(
    paths: list[Path],
    evaluation: AgentEvaluation,
    label: str,
) -> list[str]:
    lines = [f"{label} breakdown:"]
    for path, score, profit, drawdown in zip(
        paths,
        evaluation.dataset_scores,
        evaluation.dataset_profits,
        evaluation.dataset_drawdowns,
    ):
        lines.append(
            f"  {path.relative_to(DATA_ROOT)} -> "
            f"score={score:.4f} | "
            f"profit={profit:.4f} | "
            f"dd={drawdown:.4f}"
        )
    return lines


def append_lines(log_file_path: Path, lines: list[str]) -> None:
    with log_file_path.open("a", encoding="utf-8") as log_file:
        log_file.write("\n".join(lines) + "\n")


def execute_historical_run(config_path: Path) -> HistoricalRunSummary:
    config = load_run_config(str(config_path))

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

    RUN_LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file_path = RUN_LOG_DIR / f"run_{run_id}.txt"

    header_lines = [
        f"Config path: {config_path}",
        f"Run ID: {run_id}",
        f"Mutation seed: {config.mutation_seed}",
        f"Population size: {config.population_size}",
        f"Target population size: {config.target_population_size}",
        f"Survivors count: {config.survivors_count}",
        f"Generations planned: {config.generations_planned}",
        f"Datasets -> train={len(train_dataset_paths)} | validation={len(validation_dataset_paths)}",
        f"Train datasets: {format_dataset_list(train_dataset_paths)}",
        f"Validation datasets: {format_dataset_list(validation_dataset_paths)}",
        "",
    ]
    append_lines(log_file_path, header_lines)

    print(f"Run ID: {run_id}")
    print(
        f"Datasets -> train={len(train_dataset_paths)} | "
        f"validation={len(validation_dataset_paths)}"
    )
    print(f"Writing detailed log to {log_file_path}")

    random_generator = random.Random(config.mutation_seed)

    best_train_selection_score = float("-inf")
    best_genome_repr = ""
    final_validation_selection_score = float("-inf")
    final_validation_profit = 0.0
    final_validation_drawdown = 0.0
    final_validation_trades = 0.0
    

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

        generation_lines = [
            "",
            f"Generation {generation_number}",
            f"Train sample -> {format_dataset_list(sampled_train_paths)}",
            (
                f"Selection scores -> best={train_best:.4f} | "
                f"average={train_average:.4f}"
            ),
            f"Best genome -> {best_agent.genome}",
            format_evaluation("Train", best_train_evaluation),
            format_evaluation("Validation", validation_evaluation),
        ]

        generation_lines.extend(
            build_dataset_breakdown_lines(
                sampled_train_paths,
                best_train_evaluation,
                "Train",
            )
        )
        generation_lines.extend(
            build_dataset_breakdown_lines(
                validation_dataset_paths,
                validation_evaluation,
                "Validation",
            )
        )

        if best_train_evaluation.violations:
            generation_lines.append(
                f"Train violations -> {', '.join(best_train_evaluation.violations)}"
            )

        if validation_evaluation.violations:
            generation_lines.append(
                f"Validation violations -> {', '.join(validation_evaluation.violations)}"
            )

        append_lines(log_file_path, generation_lines)

        print(
            f"Generation {generation_number} | "
            f"best={train_best:.4f} | "
            f"validation_profit={validation_evaluation.median_profit:.4f} | "
            f"log={log_file_path.name}"
        )

        if best_train_evaluation.selection_score > best_train_selection_score:
            best_train_selection_score = best_train_evaluation.selection_score
            best_genome_repr = repr(best_agent.genome)
            generation_of_best = generation_number

        final_validation_selection_score = validation_evaluation.selection_score
        final_validation_profit = validation_evaluation.median_profit
        final_validation_drawdown = validation_evaluation.median_drawdown
        final_validation_trades = validation_evaluation.median_trades

        if generation_number < config.generations_planned:
            population = runner.build_next_generation(
                evaluated_agents=evaluated_agents,
                survivors_count=config.survivors_count,
                target_population_size=config.target_population_size,
            )

    summary_lines = [
        "",
        "Final summary",
        f"Best train selection score: {best_train_selection_score:.4f}",
        f"Final validation selection score: {final_validation_selection_score:.4f}",
        f"Final validation profit: {final_validation_profit:.4f}",
        f"Final validation drawdown: {final_validation_drawdown:.4f}",
        f"Final validation trades: {final_validation_trades:.1f}",
        f"Best genome found: {best_genome_repr}",
        f"Generation of best genome: {generation_of_best}",
    ]
    append_lines(log_file_path, summary_lines)

    print(f"Detailed run log saved to {log_file_path}")

    return HistoricalRunSummary(
        config_name=config_path.name,
        run_id=run_id,
        log_file_path=log_file_path,
        best_train_selection_score=best_train_selection_score,
        final_validation_selection_score=final_validation_selection_score,
        final_validation_profit=final_validation_profit,
        final_validation_drawdown=final_validation_drawdown,
        final_validation_trades=final_validation_trades,
        best_genome_repr=best_genome_repr,
        generation_of_best=generation_of_best,

    )

def main() -> None:
    execute_historical_run(Path("configs/run_config.json"))


if __name__ == "__main__":
    main()
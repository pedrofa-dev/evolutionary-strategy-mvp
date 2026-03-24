import argparse
import json
import random
import time
import uuid
from dataclasses import replace
from hashlib import sha256
from pathlib import Path

from evo_system.domain.agent import Agent
from evo_system.domain.agent_evaluation import AgentEvaluation
from evo_system.domain.genome import Genome
from evo_system.domain.run_record import RunRecord
from evo_system.domain.run_summary import HistoricalRunSummary
from evo_system.environment.csv_loader import load_historical_candles
from evo_system.environment.dataset_pool_loader import DatasetPoolLoader
from evo_system.environment.historical_environment import HistoricalEnvironment
from evo_system.orchestration.agent_evaluator import AgentEvaluator
from evo_system.orchestration.config_loader import load_run_config
from evo_system.orchestration.runner import EvolutionRunner
from evo_system.storage.sqlite_store import SQLiteStore
from experiment_presets import (
    apply_preset_to_config_data,
    get_available_preset_names,
    get_preset_by_name,
)


DEFAULT_DATASET_ROOT = Path("data/processed")
TRAIN_SAMPLE_SIZE = 4
RUN_LOG_DIR = Path("artifacts/runs")

TRAIN_WEIGHT = 0.30
VALIDATION_WEIGHT = 0.70
OVERFIT_GAP_WEIGHT = 0.75
UNDERFIT_GAP_WEIGHT = 0.50
VALIDATION_DISPERSION_WEIGHT = 0.50
INVALID_VALIDATION_PENALTY = 5.0
NEGATIVE_VALIDATION_PENALTY = 2.0

CHAMPION_MIN_VALIDATION_SELECTION = 1.5
CHAMPION_MIN_VALIDATION_PROFIT = 0.0018
CHAMPION_MAX_VALIDATION_DRAWDOWN = 0.0015
CHAMPION_MIN_VALIDATION_TRADES = 8.0
CHAMPION_MAX_ABS_SELECTION_GAP = 1.0


def build_random_genome(random_generator: random.Random) -> Genome:
    threshold_open = random_generator.uniform(0.35, 0.90)
    threshold_close = random_generator.uniform(0.05, min(0.45, threshold_open))

    use_momentum = random_generator.choice([True, False])
    use_trend = random_generator.choice([True, False])
    use_exit_momentum = random_generator.choice([True, False])

    ret_short_window = random_generator.randint(1, 5)
    ret_mid_window = random_generator.randint(max(2, ret_short_window + 1), 20)

    vol_short_window = random_generator.randint(2, 8)
    vol_long_window = random_generator.randint(max(3, vol_short_window + 1), 30)

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
        ret_short_window=ret_short_window,
        ret_mid_window=ret_mid_window,
        ma_window=random_generator.randint(3, 25),
        range_window=random_generator.randint(3, 20),
        vol_short_window=vol_short_window,
        vol_long_window=vol_long_window,
        weight_ret_short=random_generator.uniform(-1.5, 1.5),
        weight_ret_mid=random_generator.uniform(-1.5, 1.5),
        weight_dist_ma=random_generator.uniform(-1.5, 1.5),
        weight_range_pos=random_generator.uniform(-1.5, 1.5),
        weight_vol_ratio=random_generator.uniform(-1.5, 1.5),
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

    return genome


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
            threshold_open=0.40,
            threshold_close=0.12,
            position_size=0.12,
            stop_loss=0.03,
            take_profit=0.08,
            ret_short_window=1,
            ret_mid_window=3,
            ma_window=5,
            range_window=4,
            vol_short_window=2,
            vol_long_window=6,
            weight_ret_short=1.1,
            weight_ret_mid=0.7,
            weight_dist_ma=0.4,
            weight_range_pos=0.2,
            weight_vol_ratio=-0.1,
            use_exit_momentum=True,
            exit_momentum_threshold=-0.0006,
        ),
        Genome(
            threshold_open=0.42,
            threshold_close=0.14,
            position_size=0.12,
            stop_loss=0.03,
            take_profit=0.09,
            ret_short_window=2,
            ret_mid_window=5,
            ma_window=6,
            range_window=5,
            vol_short_window=2,
            vol_long_window=7,
            weight_ret_short=-0.8,
            weight_ret_mid=0.9,
            weight_dist_ma=-0.5,
            weight_range_pos=0.6,
            weight_vol_ratio=0.2,
            use_exit_momentum=True,
            exit_momentum_threshold=-0.0007,
        ),
        Genome(
            threshold_open=0.38,
            threshold_close=0.10,
            position_size=0.10,
            stop_loss=0.025,
            take_profit=0.07,
            ret_short_window=1,
            ret_mid_window=4,
            ma_window=8,
            range_window=6,
            vol_short_window=2,
            vol_long_window=8,
            weight_ret_short=0.5,
            weight_ret_mid=1.2,
            weight_dist_ma=0.3,
            weight_range_pos=-0.4,
            weight_vol_ratio=0.4,
            use_momentum=True,
            momentum_threshold=0.0003,
            use_exit_momentum=True,
            exit_momentum_threshold=-0.0005,
        ),
        Genome(
            threshold_open=0.44,
            threshold_close=0.16,
            position_size=0.14,
            stop_loss=0.04,
            take_profit=0.10,
            ret_short_window=2,
            ret_mid_window=6,
            ma_window=10,
            range_window=6,
            vol_short_window=3,
            vol_long_window=9,
            weight_ret_short=-0.6,
            weight_ret_mid=-0.3,
            weight_dist_ma=0.9,
            weight_range_pos=0.5,
            weight_vol_ratio=-0.2,
            use_trend=True,
            trend_threshold=0.0004,
            trend_window=3,
            use_exit_momentum=True,
            exit_momentum_threshold=-0.0006,
        ),
    ]

    genomes = list(base_genomes)

    while len(genomes) < population_size:
        genomes.append(build_random_genome(random_generator))

    selected_genomes = genomes[:population_size]
    return [Agent.create(genome) for genome in selected_genomes]


def build_environment(
    dataset_path: Path,
    trade_cost_rate: float,
) -> HistoricalEnvironment:
    candles = load_historical_candles(dataset_path)
    return HistoricalEnvironment(candles, trade_cost_rate=trade_cost_rate)


def summarize_generation_scores(
    selection_scores: list[float],
) -> tuple[float, float]:
    best_score = max(selection_scores)
    average_score = sum(selection_scores) / len(selection_scores)
    return best_score, average_score


def format_dataset_path(path: Path, dataset_root: Path) -> str:
    try:
        return str(path.relative_to(dataset_root))
    except ValueError:
        return str(path)


def format_dataset_list(paths: list[Path], dataset_root: Path) -> str:
    return ", ".join(format_dataset_path(path, dataset_root) for path in paths)


def build_dataset_signature(
    all_train_dataset_paths: list[Path],
    validation_dataset_paths: list[Path],
    dataset_root: Path,
    train_sample_size: int,
) -> str:
    normalized_train_names = sorted(
        format_dataset_path(path, dataset_root) for path in all_train_dataset_paths
    )
    normalized_validation_names = sorted(
        format_dataset_path(path, dataset_root) for path in validation_dataset_paths
    )
    signature_source = {
        "dataset_root": str(dataset_root),
        "train_sample_size": train_sample_size,
        "all_train_dataset_names": normalized_train_names,
        "all_validation_dataset_names": normalized_validation_names,
    }
    return sha256(
        json.dumps(signature_source, sort_keys=True).encode("utf-8")
    ).hexdigest()


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
    dataset_root: Path,
) -> list[str]:
    lines = [f"{label} breakdown:"]
    for path, score, profit, drawdown in zip(
        paths,
        evaluation.dataset_scores,
        evaluation.dataset_profits,
        evaluation.dataset_drawdowns,
    ):
        lines.append(
            f"  {format_dataset_path(path, dataset_root)} -> "
            f"score={score:.4f} | "
            f"profit={profit:.4f} | "
            f"dd={drawdown:.4f}"
        )
    return lines


def append_lines(log_file_path: Path, lines: list[str]) -> None:
    with log_file_path.open("a", encoding="utf-8") as log_file:
        log_file.write("\n".join(lines) + "\n")


def load_config_data(config_path: Path) -> dict:
    return json.loads(config_path.read_text(encoding="utf-8"))


def build_evolution_selection_score(
    train_evaluation: AgentEvaluation,
    validation_evaluation: AgentEvaluation,
) -> float:
    selection_gap = (
        train_evaluation.selection_score
        - validation_evaluation.selection_score
    )

    overfit_penalty = max(0.0, selection_gap)
    underfit_penalty = max(0.0, -selection_gap)
    validation_dispersion_penalty = validation_evaluation.dispersion

    score = (
        TRAIN_WEIGHT * train_evaluation.selection_score
        + VALIDATION_WEIGHT * validation_evaluation.selection_score
        - OVERFIT_GAP_WEIGHT * overfit_penalty
        - UNDERFIT_GAP_WEIGHT * underfit_penalty
        - VALIDATION_DISPERSION_WEIGHT * validation_dispersion_penalty
    )

    if not validation_evaluation.is_valid:
        score -= INVALID_VALIDATION_PENALTY

    if validation_evaluation.selection_score < 0.0:
        score -= NEGATIVE_VALIDATION_PENALTY

    return score


def is_champion(
    train_evaluation: AgentEvaluation,
    validation_evaluation: AgentEvaluation,
) -> bool:
    selection_gap = (
        train_evaluation.selection_score
        - validation_evaluation.selection_score
    )

    return (
        validation_evaluation.selection_score >= CHAMPION_MIN_VALIDATION_SELECTION
        and validation_evaluation.median_profit >= CHAMPION_MIN_VALIDATION_PROFIT
        and validation_evaluation.median_drawdown <= CHAMPION_MAX_VALIDATION_DRAWDOWN
        and validation_evaluation.median_trades >= CHAMPION_MIN_VALIDATION_TRADES
        and abs(selection_gap) <= CHAMPION_MAX_ABS_SELECTION_GAP
    )


def build_champion_metrics(
    train_evaluation: AgentEvaluation,
    validation_evaluation: AgentEvaluation,
    train_dataset_paths: list[Path],
    validation_dataset_paths: list[Path],
    all_train_dataset_paths: list[Path],
    config_name: str,
    context_name: str | None,
    dataset_root: Path,
) -> dict:
    selection_gap = (
        train_evaluation.selection_score
        - validation_evaluation.selection_score
    )
    sampled_train_dataset_names = [
        format_dataset_path(path, dataset_root) for path in train_dataset_paths
    ]
    validation_dataset_names = [
        format_dataset_path(path, dataset_root) for path in validation_dataset_paths
    ]
    all_train_dataset_names = [
        format_dataset_path(path, dataset_root) for path in all_train_dataset_paths
    ]
    dataset_signature = build_dataset_signature(
        all_train_dataset_paths=all_train_dataset_paths,
        validation_dataset_paths=validation_dataset_paths,
        dataset_root=dataset_root,
        train_sample_size=len(train_dataset_paths),
    )

    return {
        "config_name": config_name,
        "context_name": context_name,
        "dataset_root": str(dataset_root),
        "train_sample_size": len(train_dataset_paths),
        "train_dataset_count_available": len(all_train_dataset_paths),
        "validation_dataset_count_available": len(validation_dataset_paths),
        "all_train_dataset_names": all_train_dataset_names,
        "all_validation_dataset_names": validation_dataset_names,
        "sampled_train_dataset_names": sampled_train_dataset_names,
        # Legacy alias kept for backward-compatible analyzers and old exports.
        "validation_dataset_names": validation_dataset_names,
        "dataset_signature": dataset_signature,
        "train_selection": train_evaluation.selection_score,
        "train_profit": train_evaluation.median_profit,
        "train_drawdown": train_evaluation.median_drawdown,
        "train_trades": train_evaluation.median_trades,
        "validation_selection": validation_evaluation.selection_score,
        "validation_profit": validation_evaluation.median_profit,
        "validation_drawdown": validation_evaluation.median_drawdown,
        "validation_trades": validation_evaluation.median_trades,
        "selection_gap": selection_gap,
        "validation_dispersion": validation_evaluation.dispersion,
        "train_dataset_scores": train_evaluation.dataset_scores,
        "train_dataset_profits": train_evaluation.dataset_profits,
        "train_dataset_drawdowns": train_evaluation.dataset_drawdowns,
        "validation_dataset_scores": validation_evaluation.dataset_scores,
        "validation_dataset_profits": validation_evaluation.dataset_profits,
        "validation_dataset_drawdowns": validation_evaluation.dataset_drawdowns,
        "train_dataset_names": sampled_train_dataset_names,
        "train_violations": train_evaluation.violations,
        "validation_violations": validation_evaluation.violations,
        "train_is_valid": train_evaluation.is_valid,
        "validation_is_valid": validation_evaluation.is_valid,
    }


def execute_historical_run(
    config_path: Path,
    output_dir: Path | None = None,
    log_name: str | None = None,
    config_name_override: str | None = None,
    dataset_root: Path = DEFAULT_DATASET_ROOT,
    context_name: str | None = None,
    generations_override: int | None = None,
) -> HistoricalRunSummary:
    run_start_time = time.perf_counter()

    config = load_run_config(str(config_path))
    if generations_override is not None:
        config = replace(config, generations_planned=generations_override)
    config_name = config_name_override or config_path.name

    evaluator = AgentEvaluator(cost_penalty_weight=config.cost_penalty_weight)
    loader = DatasetPoolLoader()
    train_dataset_paths, validation_dataset_paths = loader.load_paths(dataset_root)
    dataset_signature = build_dataset_signature(
        all_train_dataset_paths=train_dataset_paths,
        validation_dataset_paths=validation_dataset_paths,
        dataset_root=dataset_root,
        train_sample_size=min(TRAIN_SAMPLE_SIZE, len(train_dataset_paths)),
    )

    run_id = str(uuid.uuid4())

    runner = EvolutionRunner(
        mutation_seed=config.mutation_seed,
        mutation_profile=config.mutation_profile,
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

    if output_dir is None:
        output_dir = RUN_LOG_DIR

    output_dir.mkdir(parents=True, exist_ok=True)

    if log_name is None:
        log_name = f"run_{run_id}.txt"

    log_file_path = output_dir / log_name

    header_lines = [
        f"Config path: {config_path}",
        f"Config name: {config_name}",
        f"Context name: {context_name or 'none'}",
        f"Run ID: {run_id}",
        f"Dataset root: {dataset_root}",
        f"Dataset signature: {dataset_signature}",
        f"Mutation seed: {config.mutation_seed}",
        f"Mutation profile: {config.mutation_profile}",
        f"Population size: {config.population_size}",
        f"Target population size: {config.target_population_size}",
        f"Survivors count: {config.survivors_count}",
        f"Generations planned: {config.generations_planned}",
        f"Trade cost rate: {config.trade_cost_rate}",
        f"Cost penalty weight: {config.cost_penalty_weight}",
        f"Datasets -> train={len(train_dataset_paths)} | validation={len(validation_dataset_paths)}",
        f"Train sample size per generation: {min(TRAIN_SAMPLE_SIZE, len(train_dataset_paths))}",
        f"Train datasets: {format_dataset_list(train_dataset_paths, dataset_root)}",
        f"Validation datasets: {format_dataset_list(validation_dataset_paths, dataset_root)}",
        (
            f"Evolution score weights -> train={TRAIN_WEIGHT:.2f} | "
            f"validation={VALIDATION_WEIGHT:.2f} | "
            f"overfit_gap_penalty={OVERFIT_GAP_WEIGHT:.2f} | "
            f"underfit_gap_penalty={UNDERFIT_GAP_WEIGHT:.2f} | "
            f"validation_dispersion_penalty={VALIDATION_DISPERSION_WEIGHT:.2f}"
        ),
        "",
    ]
    append_lines(log_file_path, header_lines)

    print(f"Run ID: {run_id}")
    print(f"Config name: {config_name}")
    if context_name:
        print(f"Context name: {context_name}")
    print(f"Dataset root: {dataset_root}")
    print(f"Dataset signature: {dataset_signature}")
    print(f"Mutation profile: {config.mutation_profile}")
    print(
        f"Datasets -> train={len(train_dataset_paths)} | "
        f"validation={len(validation_dataset_paths)}"
    )
    print(f"Trade cost rate: {config.trade_cost_rate}")
    print(f"Cost penalty weight: {config.cost_penalty_weight}")
    print(f"Writing log to {log_file_path}")

    random_generator = random.Random(config.mutation_seed)

    best_train_selection_score = float("-inf")
    best_train_profit = 0.0
    best_genome_repr = ""
    final_validation_selection_score = float("-inf")
    final_validation_profit = 0.0
    final_validation_drawdown = 0.0
    final_validation_trades = 0.0
    generation_of_best = 0

    generation_durations: list[float] = []

    for generation_number in range(1, config.generations_planned + 1):
        generation_start_time = time.perf_counter()

        sampled_train_paths = random_generator.sample(
            train_dataset_paths,
            k=min(TRAIN_SAMPLE_SIZE, len(train_dataset_paths)),
        )

        train_environments = [
            build_environment(path, trade_cost_rate=config.trade_cost_rate)
            for path in sampled_train_paths
        ]
        validation_environments = [
            build_environment(path, trade_cost_rate=config.trade_cost_rate)
            for path in validation_dataset_paths
        ]

        evaluated_agents: list[tuple[Agent, float]] = []
        train_evaluations: dict[str, AgentEvaluation] = {}
        validation_evaluations: dict[str, AgentEvaluation] = {}

        eval_start_time = time.perf_counter()

        for agent in population:
            train_evaluation = evaluator.evaluate(
                agent=agent,
                environments=train_environments,
            )
            validation_evaluation = evaluator.evaluate(
                agent=agent,
                environments=validation_environments,
            )

            evolution_selection_score = build_evolution_selection_score(
                train_evaluation=train_evaluation,
                validation_evaluation=validation_evaluation,
            )

            evaluated_agents.append((agent, evolution_selection_score))
            train_evaluations[agent.id] = train_evaluation
            validation_evaluations[agent.id] = validation_evaluation

        eval_duration = time.perf_counter() - eval_start_time

        summary = runner.summarize_generation(
            generation_number=generation_number,
            evaluated_agents=evaluated_agents,
        )
        store.save_generation_result(run_id, summary)

        best_agent, best_evolution_score = max(
            evaluated_agents,
            key=lambda item: item[1],
        )
        best_train_evaluation = train_evaluations[best_agent.id]
        best_validation_evaluation = validation_evaluations[best_agent.id]

        train_best, train_average = summarize_generation_scores(
            [evaluation.selection_score for evaluation in train_evaluations.values()]
        )
        validation_best, validation_average = summarize_generation_scores(
            [evaluation.selection_score for evaluation in validation_evaluations.values()]
        )
        evolution_best, evolution_average = summarize_generation_scores(
            [score for _, score in evaluated_agents]
        )

        next_generation_duration = 0.0
        next_population: list[Agent] | None = None

        if generation_number < config.generations_planned:
            next_generation_start_time = time.perf_counter()
            next_population = runner.build_next_generation(
                evaluated_agents=evaluated_agents,
                survivors_count=config.survivors_count,
                target_population_size=config.target_population_size,
            )
            next_generation_duration = time.perf_counter() - next_generation_start_time

        generation_duration = time.perf_counter() - generation_start_time
        generation_durations.append(generation_duration)

        selection_gap = (
            best_train_evaluation.selection_score
            - best_validation_evaluation.selection_score
        )
        profit_gap = (
            best_train_evaluation.median_profit
            - best_validation_evaluation.median_profit
        )

        generation_lines = [
            "",
            f"Generation {generation_number}",
            f"Train sample -> {format_dataset_list(sampled_train_paths, dataset_root)}",
            (
                f"Evolution scores -> best={evolution_best:.4f} | "
                f"average={evolution_average:.4f}"
            ),
            (
                f"Train selection -> best={train_best:.4f} | "
                f"average={train_average:.4f}"
            ),
            (
                f"Validation selection -> best={validation_best:.4f} | "
                f"average={validation_average:.4f}"
            ),
            (
                f"Gaps -> selection_gap={selection_gap:.4f} | "
                f"profit_gap={profit_gap:.4f}"
            ),
            (
                f"Validation dispersion -> {best_validation_evaluation.dispersion:.4f}"
            ),
            (
                f"Timing -> total={generation_duration:.2f}s | "
                f"all_eval={eval_duration:.2f}s | "
                f"next_generation={next_generation_duration:.2f}s"
            ),
            f"Best genome -> {best_agent.genome}",
            f"Evolution selection score -> {best_evolution_score:.4f}",
            format_evaluation("Train", best_train_evaluation),
            format_evaluation("Validation", best_validation_evaluation),
        ]

        generation_lines.extend(
            build_dataset_breakdown_lines(
                sampled_train_paths,
                best_train_evaluation,
                "Train",
                dataset_root,
            )
        )
        generation_lines.extend(
            build_dataset_breakdown_lines(
                validation_dataset_paths,
                best_validation_evaluation,
                "Validation",
                dataset_root,
            )
        )

        if best_train_evaluation.violations:
            generation_lines.append(
                f"Train violations -> {', '.join(best_train_evaluation.violations)}"
            )

        if best_validation_evaluation.violations:
            generation_lines.append(
                f"Validation violations -> {', '.join(best_validation_evaluation.violations)}"
            )

        is_final_generation = generation_number == config.generations_planned
        saved_as_champion = False

        if is_final_generation and is_champion(
            train_evaluation=best_train_evaluation,
            validation_evaluation=best_validation_evaluation,
        ):
            champion_metrics = build_champion_metrics(
                train_evaluation=best_train_evaluation,
                validation_evaluation=best_validation_evaluation,
                train_dataset_paths=sampled_train_paths,
                validation_dataset_paths=validation_dataset_paths,
                all_train_dataset_paths=train_dataset_paths,
                config_name=config_name,
                context_name=context_name,
                dataset_root=dataset_root,
            )
            store.save_champion(
                run_id=run_id,
                generation_number=generation_number,
                mutation_seed=config.mutation_seed,
                config_name=config_name,
                genome=best_agent.genome,
                metrics=champion_metrics,
            )
            saved_as_champion = True
            generation_lines.append("Champion persisted -> yes")
            generation_lines.append(
                "Champion context -> "
                f"config_name={champion_metrics['config_name']} | "
                f"context_name={champion_metrics['context_name'] or 'none'} | "
                f"dataset_root={champion_metrics['dataset_root']} | "
                f"train_sample_size={champion_metrics['train_sample_size']} | "
                f"train_dataset_count_available={champion_metrics['train_dataset_count_available']} | "
                f"validation_dataset_count_available={champion_metrics['validation_dataset_count_available']} | "
                f"dataset_signature={champion_metrics['dataset_signature']}"
            )
        elif is_final_generation:
            generation_lines.append("Champion persisted -> no")

        append_lines(log_file_path, generation_lines)

        print(
            f"Generation {generation_number} | "
            f"evolution_best={evolution_best:.4f} | "
            f"train_profit={best_train_evaluation.median_profit:.4f} | "
            f"validation_selection={best_validation_evaluation.selection_score:.4f} | "
            f"validation_profit={best_validation_evaluation.median_profit:.4f} | "
            f"validation_dispersion={best_validation_evaluation.dispersion:.4f} | "
            f"selection_gap={selection_gap:.4f} | "
            f"profit_gap={profit_gap:.4f} | "
            f"champion_saved={saved_as_champion} | "
            f"time={generation_duration:.2f}s | "
            f"log={log_file_path.name}"
        )

        if best_evolution_score > float("-inf"):
            best_train_selection_score = best_train_evaluation.selection_score
            best_train_profit = best_train_evaluation.median_profit
            best_genome_repr = repr(best_agent.genome)
            generation_of_best = generation_number

        final_validation_selection_score = best_validation_evaluation.selection_score
        final_validation_profit = best_validation_evaluation.median_profit
        final_validation_drawdown = best_validation_evaluation.median_drawdown
        final_validation_trades = best_validation_evaluation.median_trades

        if next_population is not None:
            population = next_population

    total_run_duration = time.perf_counter() - run_start_time
    average_generation_duration = (
        sum(generation_durations) / len(generation_durations)
        if generation_durations
        else 0.0
    )

    train_validation_selection_gap = (
        best_train_selection_score - final_validation_selection_score
    )
    train_validation_profit_gap = best_train_profit - final_validation_profit

    summary_lines = [
        "",
        "Final summary",
        f"Best train selection score: {best_train_selection_score:.4f}",
        f"Best train profit: {best_train_profit:.4f}",
        f"Final validation selection score: {final_validation_selection_score:.4f}",
        f"Final validation profit: {final_validation_profit:.4f}",
        f"Final validation drawdown: {final_validation_drawdown:.4f}",
        f"Final validation trades: {final_validation_trades:.1f}",
        f"Final selection gap: {train_validation_selection_gap:.4f}",
        f"Final profit gap: {train_validation_profit_gap:.4f}",
        f"Best genome found: {best_genome_repr}",
        f"Generation of best genome: {generation_of_best}",
        f"Total run time: {total_run_duration:.2f}s",
        f"Average generation time: {average_generation_duration:.2f}s",
    ]
    append_lines(log_file_path, summary_lines)

    print(f"Total run time: {total_run_duration:.2f}s")
    print(f"Average generation time: {average_generation_duration:.2f}s")
    print(f"Detailed run log saved to {log_file_path}")

    return HistoricalRunSummary(
        config_name=config_name,
        run_id=run_id,
        log_file_path=log_file_path,
        mutation_seed=config.mutation_seed,
        best_train_selection_score=best_train_selection_score,
        final_validation_selection_score=final_validation_selection_score,
        final_validation_profit=final_validation_profit,
        final_validation_drawdown=final_validation_drawdown,
        final_validation_trades=final_validation_trades,
        best_genome_repr=best_genome_repr,
        generation_of_best=generation_of_best,
        train_validation_selection_gap=train_validation_selection_gap,
        train_validation_profit_gap=train_validation_profit_gap,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Execute a single historical run.")
    parser.add_argument(
        "--config-path",
        type=Path,
        default=Path("configs/run_config.json"),
        help="Path to the run config JSON.",
    )
    parser.add_argument(
        "--preset",
        type=str,
        choices=get_available_preset_names(),
        default=None,
        help="Optional execution preset overriding generations only.",
    )
    args = parser.parse_args()

    preset = get_preset_by_name(args.preset)
    generations_override: int | None = None

    if preset is not None:
        preset_config = apply_preset_to_config_data(
            load_config_data(args.config_path),
            preset,
        )
        generations_override = int(preset_config["generations_planned"])
        print(
            f"Using preset '{preset.name}' -> generations={generations_override}"
        )

    execute_historical_run(
        config_path=args.config_path,
        dataset_root=DEFAULT_DATASET_ROOT,
        generations_override=generations_override,
    )


if __name__ == "__main__":
    main()

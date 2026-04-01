import json
import random
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from evo_system.champions import (
    build_champion_metrics,
    classify_champion,
    is_better_persistable_champion,
    should_persist_champion,
)
from evo_system.champions.metrics import (
    build_dataset_signature,
    format_dataset_path,
)
from evo_system.domain.agent import Agent
from evo_system.domain.agent_evaluation import AgentEvaluation
from evo_system.domain.genome import (
    EntryContextGene,
    EntryTriggerGene,
    ExitPolicyGene,
    Genome,
    TradeControlGene,
    build_policy_v2_genome,
)
from evo_system.domain.run_summary import HistoricalRunSummary
from evo_system.environment.csv_loader import load_historical_candles
from evo_system.environment.dataset_pool_loader import DatasetPoolLoader
from evo_system.environment.historical_environment import HistoricalEnvironment
from evo_system.evaluation import (
    AgentEvaluator,
    INVALID_VALIDATION_PENALTY,
    NEGATIVE_VALIDATION_PENALTY,
    build_evolution_selection_score,
)
from evo_system.evaluation.scoring import (
    OVERFIT_GAP_WEIGHT,
    TRAIN_WEIGHT,
    UNDERFIT_GAP_WEIGHT,
    VALIDATION_DISPERSION_WEIGHT,
    VALIDATION_WEIGHT,
)
from evo_system.experimentation.external_validation import (
    build_external_validation_metrics,
    run_external_validation,
)
from evo_system.experimentation.dataset_roots import (
    DEFAULT_DATASET_ROOT,
    resolve_dataset_root,
)
from evo_system.experimentation.parallel_progress import write_progress_snapshot
from evo_system.orchestration.config_loader import load_run_config
from evo_system.orchestration.runner import EvolutionRunner
from evo_system.storage import (
    CURRENT_LOGIC_VERSION,
    DEFAULT_PERSISTENCE_DB_PATH,
    PersistenceStore,
)
DEFAULT_EXTERNAL_VALIDATION_DIR = DEFAULT_DATASET_ROOT / "external_validation"
TRAIN_SAMPLE_SIZE = 4
RUN_LOG_DIR = Path("artifacts/runs")


@dataclass(frozen=True)
class PersistableChampionCandidate:
    genome: Genome
    champion_type: str
    generation_number: int
    mutation_seed: int
    train_evaluation: AgentEvaluation
    validation_evaluation: AgentEvaluation
    train_dataset_paths: list[Path]
    validation_dataset_paths: list[Path]
    all_train_dataset_paths: list[Path]
    config_name: str
    context_name: str | None
    dataset_root: Path


def build_random_genome(
    random_generator: random.Random,
    entry_score_margin: float = 0.0,
    min_bars_between_entries: int = 0,
    entry_confirmation_bars: int = 1,
    entry_trigger_overrides: dict[str, Any] | None = None,
) -> Genome:
    ret_short_window = random_generator.randint(1, 5)
    ret_mid_window = random_generator.randint(max(2, ret_short_window + 1), 20)
    vol_short_window = random_generator.randint(2, 8)
    vol_long_window = random_generator.randint(max(3, vol_short_window + 1), 30)

    genome = build_policy_v2_genome(
        position_size=random_generator.uniform(0.05, 0.25),
        stop_loss_pct=random_generator.uniform(0.01, 0.06),
        take_profit_pct=random_generator.uniform(0.03, 0.18),
        trend_window=random_generator.randint(2, 8),
        ret_short_window=ret_short_window,
        ret_mid_window=ret_mid_window,
        ma_window=random_generator.randint(3, 25),
        range_window=random_generator.randint(3, 20),
        vol_short_window=vol_short_window,
        vol_long_window=vol_long_window,
        entry_context=EntryContextGene(),
        entry_trigger=EntryTriggerGene(
            trend_weight=random_generator.uniform(-1.5, 1.5),
            momentum_weight=random_generator.uniform(-1.5, 1.5),
            breakout_weight=random_generator.uniform(-1.5, 1.5),
            range_weight=random_generator.uniform(-1.5, 1.5),
            volatility_weight=random_generator.uniform(-1.5, 1.5),
            entry_score_threshold=random_generator.uniform(0.35, 0.90),
            min_positive_families=random_generator.randint(1, 3),
            require_trend_or_breakout=True,
        ),
        exit_policy=ExitPolicyGene(
            exit_score_threshold=random_generator.uniform(-0.10, 0.20),
            exit_on_signal_reversal=random_generator.choice([True, False]),
            max_holding_bars=random_generator.choice([0, 12, 24, 36]),
            stop_loss_pct=random_generator.uniform(0.01, 0.06),
            take_profit_pct=random_generator.uniform(0.03, 0.18),
        ),
        trade_control=TradeControlGene(),
    )

    return _apply_entry_trigger_overrides(genome, entry_trigger_overrides)


def build_initial_population(
    population_size: int,
    entry_score_margin: float = 0.0,
    min_bars_between_entries: int = 0,
    entry_confirmation_bars: int = 1,
    entry_trigger_overrides: dict[str, Any] | None = None,
) -> list[Agent]:
    if population_size <= 0:
        raise ValueError("population_size must be greater than 0")

    random_generator = random.Random(12345)

    base_genomes = [
        build_policy_v2_genome(
            position_size=0.20,
            stop_loss_pct=0.05,
            take_profit_pct=0.10,
            entry_trigger=EntryTriggerGene(
                trend_weight=0.3,
                momentum_weight=0.2,
                breakout_weight=0.7,
                range_weight=0.0,
                volatility_weight=0.0,
                entry_score_threshold=0.80,
                min_positive_families=2,
                require_trend_or_breakout=True,
            ),
            exit_policy=ExitPolicyGene(
                exit_score_threshold=0.10,
                exit_on_signal_reversal=True,
                stop_loss_pct=0.05,
                take_profit_pct=0.10,
            ),
        ),
        build_policy_v2_genome(
            position_size=0.16,
            stop_loss_pct=0.04,
            take_profit_pct=0.10,
            entry_trigger=EntryTriggerGene(
                trend_weight=0.4,
                momentum_weight=0.9,
                breakout_weight=0.4,
                range_weight=0.0,
                volatility_weight=0.0,
                entry_score_threshold=0.72,
                min_positive_families=2,
                require_trend_or_breakout=True,
            ),
            exit_policy=ExitPolicyGene(
                exit_score_threshold=0.08,
                exit_on_signal_reversal=True,
                stop_loss_pct=0.04,
                take_profit_pct=0.10,
            ),
        ),
        build_policy_v2_genome(
            position_size=0.15,
            stop_loss_pct=0.03,
            take_profit_pct=0.09,
            trend_window=4,
            entry_trigger=EntryTriggerGene(
                trend_weight=1.0,
                momentum_weight=0.2,
                breakout_weight=0.2,
                range_weight=0.0,
                volatility_weight=0.0,
                entry_score_threshold=0.70,
                min_positive_families=2,
                require_trend_or_breakout=True,
            ),
            exit_policy=ExitPolicyGene(
                exit_score_threshold=0.05,
                exit_on_signal_reversal=True,
                stop_loss_pct=0.03,
                take_profit_pct=0.09,
            ),
        ),
        build_policy_v2_genome(
            position_size=0.10,
            stop_loss_pct=0.02,
            take_profit_pct=0.06,
            trend_window=3,
            entry_trigger=EntryTriggerGene(
                trend_weight=0.8,
                momentum_weight=0.8,
                breakout_weight=0.2,
                range_weight=0.0,
                volatility_weight=0.0,
                entry_score_threshold=0.66,
                min_positive_families=2,
                require_trend_or_breakout=True,
            ),
            exit_policy=ExitPolicyGene(
                exit_score_threshold=0.02,
                exit_on_signal_reversal=True,
                stop_loss_pct=0.02,
                take_profit_pct=0.06,
            ),
        ),
        build_policy_v2_genome(
            position_size=0.12,
            stop_loss_pct=0.03,
            take_profit_pct=0.08,
            ret_short_window=1,
            ret_mid_window=3,
            ma_window=5,
            range_window=4,
            vol_short_window=2,
            vol_long_window=6,
            entry_trigger=EntryTriggerGene(
                trend_weight=0.4,
                momentum_weight=0.9,
                breakout_weight=0.0,
                range_weight=0.2,
                volatility_weight=-0.1,
                entry_score_threshold=0.40,
                min_positive_families=1,
                require_trend_or_breakout=False,
            ),
            exit_policy=ExitPolicyGene(
                exit_score_threshold=0.12,
                exit_on_signal_reversal=True,
                stop_loss_pct=0.03,
                take_profit_pct=0.08,
            ),
        ),
        build_policy_v2_genome(
            position_size=0.12,
            stop_loss_pct=0.03,
            take_profit_pct=0.09,
            ret_short_window=2,
            ret_mid_window=5,
            ma_window=6,
            range_window=5,
            vol_short_window=2,
            vol_long_window=7,
            entry_trigger=EntryTriggerGene(
                trend_weight=-0.5,
                momentum_weight=0.05,
                breakout_weight=0.0,
                range_weight=0.6,
                volatility_weight=0.2,
                entry_score_threshold=0.42,
                min_positive_families=1,
                require_trend_or_breakout=False,
            ),
            exit_policy=ExitPolicyGene(
                exit_score_threshold=0.14,
                exit_on_signal_reversal=True,
                stop_loss_pct=0.03,
                take_profit_pct=0.09,
            ),
        ),
        build_policy_v2_genome(
            position_size=0.10,
            stop_loss_pct=0.025,
            take_profit_pct=0.07,
            ret_short_window=1,
            ret_mid_window=4,
            ma_window=8,
            range_window=6,
            vol_short_window=2,
            vol_long_window=8,
            entry_trigger=EntryTriggerGene(
                trend_weight=0.3,
                momentum_weight=0.85,
                breakout_weight=0.0,
                range_weight=-0.4,
                volatility_weight=0.4,
                entry_score_threshold=0.38,
                min_positive_families=1,
                require_trend_or_breakout=False,
            ),
            exit_policy=ExitPolicyGene(
                exit_score_threshold=0.10,
                exit_on_signal_reversal=True,
                stop_loss_pct=0.025,
                take_profit_pct=0.07,
            ),
        ),
        build_policy_v2_genome(
            position_size=0.14,
            stop_loss_pct=0.04,
            take_profit_pct=0.10,
            ret_short_window=2,
            ret_mid_window=6,
            ma_window=10,
            range_window=6,
            vol_short_window=3,
            vol_long_window=9,
            trend_window=3,
            entry_trigger=EntryTriggerGene(
                trend_weight=0.9,
                momentum_weight=-0.45,
                breakout_weight=0.0,
                range_weight=0.5,
                volatility_weight=-0.2,
                entry_score_threshold=0.44,
                min_positive_families=1,
                require_trend_or_breakout=True,
            ),
            exit_policy=ExitPolicyGene(
                exit_score_threshold=0.16,
                exit_on_signal_reversal=True,
                stop_loss_pct=0.04,
                take_profit_pct=0.10,
            ),
        ),
    ]

    genomes = list(base_genomes)

    while len(genomes) < population_size:
        genomes.append(
            build_random_genome(
                random_generator,
                entry_score_margin=entry_score_margin,
                min_bars_between_entries=min_bars_between_entries,
                entry_confirmation_bars=entry_confirmation_bars,
            )
        )

    selected_genomes = [
        _apply_entry_trigger_overrides(genome, entry_trigger_overrides)
        for genome in genomes[:population_size]
    ]
    return [Agent.create(genome) for genome in selected_genomes]


def _apply_entry_trigger_overrides(
    genome: Genome,
    entry_trigger_overrides: dict[str, Any] | None,
) -> Genome:
    if not entry_trigger_overrides:
        return genome

    merged_trigger = dict(genome.to_dict()["entry_trigger"])
    merged_trigger.update(entry_trigger_overrides)
    return genome.copy_with(entry_trigger=merged_trigger)


def build_environment(
    dataset_path: Path,
    trade_cost_rate: float,
    regime_filter_enabled: bool = False,
    min_trend_long_for_entry: float = 0.0,
    min_breakout_for_entry: float = 0.0,
    max_realized_volatility_for_entry: float | None = None,
) -> HistoricalEnvironment:
    candles = load_historical_candles(dataset_path)
    return HistoricalEnvironment(
        candles,
        trade_cost_rate=trade_cost_rate,
        regime_filter_enabled=regime_filter_enabled,
        min_trend_long_for_entry=min_trend_long_for_entry,
        min_breakout_for_entry=min_breakout_for_entry,
        max_realized_volatility_for_entry=max_realized_volatility_for_entry,
    )


def summarize_generation_scores(
    selection_scores: list[float],
) -> tuple[float, float]:
    best_score = max(selection_scores)
    average_score = sum(selection_scores) / len(selection_scores)
    return best_score, average_score


def format_dataset_list(paths: list[Path], dataset_root: Path) -> str:
    return ", ".join(format_dataset_path(path, dataset_root) for path in paths)


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


def serialize_agent_evaluation(evaluation: AgentEvaluation) -> dict:
    return {
        "aggregated_score": evaluation.aggregated_score,
        "dispersion": evaluation.dispersion,
        "selection_score": evaluation.selection_score,
        "median_trades": evaluation.median_trades,
        "median_profit": evaluation.median_profit,
        "median_drawdown": evaluation.median_drawdown,
        "dataset_scores": evaluation.dataset_scores,
        "dataset_profits": evaluation.dataset_profits,
        "dataset_drawdowns": evaluation.dataset_drawdowns,
        "is_valid": evaluation.is_valid,
        "violations": evaluation.violations,
        "worst_dataset_score": evaluation.worst_dataset_score,
        "bottom_quartile_score": evaluation.bottom_quartile_score,
        "score_mad": evaluation.score_mad,
    }


def resolve_external_validation_dataset_paths(
    external_validation_dir: Path,
) -> list[Path]:
    return sorted(external_validation_dir.rglob("*.csv"))


def execute_historical_run(
    config_path: Path,
    output_dir: Path | None = None,
    log_name: str | None = None,
    config_name_override: str | None = None,
    dataset_root: Path = DEFAULT_DATASET_ROOT,
    context_name: str | None = None,
    external_validation_dir: Path = DEFAULT_EXTERNAL_VALIDATION_DIR,
    skip_external_validation: bool = False,
    progress_snapshot_path: Path | None = None,
    persistence_db_path: Path = DEFAULT_PERSISTENCE_DB_PATH,
    run_execution_id: int | None = None,
    config_json_snapshot: dict | None = None,
) -> HistoricalRunSummary:
    run_start_time = time.perf_counter()

    config = load_run_config(str(config_path))
    config_name = config_name_override or config_path.name
    effective_dataset_root = resolve_dataset_root(dataset_root)

    evaluator = AgentEvaluator(
        cost_penalty_weight=config.cost_penalty_weight,
        trade_count_penalty_weight=config.trade_count_penalty_weight,
    )
    loader = DatasetPoolLoader()
    train_dataset_paths, validation_dataset_paths = loader.load_paths(
        effective_dataset_root,
        dataset_catalog_id=config.dataset_catalog_id,
    )
    dataset_signature = build_dataset_signature(
        all_train_dataset_paths=train_dataset_paths,
        validation_dataset_paths=validation_dataset_paths,
        dataset_root=effective_dataset_root,
        train_sample_size=min(TRAIN_SAMPLE_SIZE, len(train_dataset_paths)),
    )

    run_id = str(uuid.uuid4())

    runner = EvolutionRunner(
        mutation_seed=config.mutation_seed,
        mutation_profile=config.mutation_profile,
    )

    population = build_initial_population(
        config.population_size,
        entry_score_margin=config.entry_score_margin,
        min_bars_between_entries=config.min_bars_between_entries,
        entry_confirmation_bars=config.entry_confirmation_bars,
        entry_trigger_overrides=config.entry_trigger_overrides,
    )

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
        f"Dataset catalog: {config.dataset_catalog_id or 'none'}",
        f"Dataset root: {effective_dataset_root}",
        f"Dataset signature: {dataset_signature}",
        f"Mutation seed: {config.mutation_seed}",
        f"Mutation profile: {config.mutation_profile}",
        f"Population size: {config.population_size}",
        f"Target population size: {config.target_population_size}",
        f"Survivors count: {config.survivors_count}",
        f"Generations planned: {config.generations_planned}",
        f"Trade cost rate: {config.trade_cost_rate}",
        f"Cost penalty weight: {config.cost_penalty_weight}",
        f"Trade count penalty weight: {config.trade_count_penalty_weight}",
        f"Entry score margin: {config.entry_score_margin:.4f}",
        f"Min bars between entries: {config.min_bars_between_entries}",
        f"Entry confirmation bars: {config.entry_confirmation_bars}",
        f"Regime filter enabled: {config.regime_filter_enabled}",
        f"Min trend long for entry: {config.min_trend_long_for_entry:.4f}",
        f"Min breakout for entry: {config.min_breakout_for_entry:.4f}",
        (
            "Max realized volatility for entry: "
            f"{config.max_realized_volatility_for_entry if config.max_realized_volatility_for_entry is not None else 'none'}"
        ),
        f"Datasets -> train={len(train_dataset_paths)} | validation={len(validation_dataset_paths)}",
        f"Train sample size per generation: {min(TRAIN_SAMPLE_SIZE, len(train_dataset_paths))}",
        f"Train datasets: {format_dataset_list(train_dataset_paths, effective_dataset_root)}",
        f"Validation datasets: {format_dataset_list(validation_dataset_paths, effective_dataset_root)}",
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
    if config.dataset_catalog_id:
        print(f"Dataset catalog: {config.dataset_catalog_id}")
    print(f"Dataset root: {effective_dataset_root}")
    print(f"Dataset signature: {dataset_signature}")
    print(f"Mutation profile: {config.mutation_profile}")
    print(
        f"Datasets -> train={len(train_dataset_paths)} | "
        f"validation={len(validation_dataset_paths)}"
    )
    print(f"Trade cost rate: {config.trade_cost_rate}")
    print(f"Cost penalty weight: {config.cost_penalty_weight}")
    print(f"Trade count penalty weight: {config.trade_count_penalty_weight}")
    print(f"Entry score margin: {config.entry_score_margin:.4f}")
    print(f"Min bars between entries: {config.min_bars_between_entries}")
    print(f"Entry confirmation bars: {config.entry_confirmation_bars}")
    print(f"Regime filter enabled: {config.regime_filter_enabled}")
    print(f"Min trend long for entry: {config.min_trend_long_for_entry:.4f}")
    print(f"Min breakout for entry: {config.min_breakout_for_entry:.4f}")
    print(
        "Max realized volatility for entry: "
        f"{config.max_realized_volatility_for_entry if config.max_realized_volatility_for_entry is not None else 'none'}"
    )
    print(f"Writing log to {log_file_path}")

    if progress_snapshot_path is not None:
        write_progress_snapshot(
            progress_snapshot_path,
            config_name=config_name,
            mutation_seed=config.mutation_seed,
            current_generation=0,
            total_generations=config.generations_planned,
            validation_selection=None,
            elapsed_seconds=time.perf_counter() - run_start_time,
        )

    random_generator = random.Random(config.mutation_seed)

    best_train_selection_score = float("-inf")
    best_train_profit = 0.0
    best_genome_repr = ""
    final_validation_selection_score = float("-inf")
    final_validation_profit = 0.0
    final_validation_drawdown = 0.0
    final_validation_trades = 0.0
    generation_of_best = 0
    best_persistable_champion: PersistableChampionCandidate | None = None

    generation_durations: list[float] = []

    for generation_number in range(1, config.generations_planned + 1):
        generation_start_time = time.perf_counter()

        sampled_train_paths = random_generator.sample(
            train_dataset_paths,
            k=min(TRAIN_SAMPLE_SIZE, len(train_dataset_paths)),
        )

        train_environments = [
            build_environment(
                path,
                trade_cost_rate=config.trade_cost_rate,
                regime_filter_enabled=config.regime_filter_enabled,
                min_trend_long_for_entry=config.min_trend_long_for_entry,
                min_breakout_for_entry=config.min_breakout_for_entry,
                max_realized_volatility_for_entry=config.max_realized_volatility_for_entry,
            )
            for path in sampled_train_paths
        ]
        validation_environments = [
            build_environment(
                path,
                trade_cost_rate=config.trade_cost_rate,
                regime_filter_enabled=config.regime_filter_enabled,
                min_trend_long_for_entry=config.min_trend_long_for_entry,
                min_breakout_for_entry=config.min_breakout_for_entry,
                max_realized_volatility_for_entry=config.max_realized_volatility_for_entry,
            )
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
                invalid_validation_penalty=INVALID_VALIDATION_PENALTY,
                negative_validation_penalty=NEGATIVE_VALIDATION_PENALTY,
            )

            evaluated_agents.append((agent, evolution_selection_score))
            train_evaluations[agent.id] = train_evaluation
            validation_evaluations[agent.id] = validation_evaluation

        eval_duration = time.perf_counter() - eval_start_time

        runner.summarize_generation(
            generation_number=generation_number,
            evaluated_agents=evaluated_agents,
        )

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
            f"Train sample -> {format_dataset_list(sampled_train_paths, effective_dataset_root)}",
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
                effective_dataset_root,
            )
        )
        generation_lines.extend(
            build_dataset_breakdown_lines(
                validation_dataset_paths,
                best_validation_evaluation,
                "Validation",
                effective_dataset_root,
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

        champion_type = classify_champion(
            train_evaluation=best_train_evaluation,
            validation_evaluation=best_validation_evaluation,
        )
        champion_tracking_updated = False

        if should_persist_champion(champion_type):
            candidate = PersistableChampionCandidate(
                genome=best_agent.genome,
                champion_type=champion_type,
                generation_number=generation_number,
                mutation_seed=config.mutation_seed,
                train_evaluation=best_train_evaluation,
                validation_evaluation=best_validation_evaluation,
                train_dataset_paths=list(sampled_train_paths),
                validation_dataset_paths=list(validation_dataset_paths),
                all_train_dataset_paths=list(train_dataset_paths),
                config_name=config_name,
                context_name=context_name,
                dataset_root=effective_dataset_root,
            )

            if best_persistable_champion is None or is_better_persistable_champion(
                candidate_train_evaluation=candidate.train_evaluation,
                candidate_validation_evaluation=candidate.validation_evaluation,
                candidate_generation_number=candidate.generation_number,
                current_train_evaluation=best_persistable_champion.train_evaluation,
                current_validation_evaluation=best_persistable_champion.validation_evaluation,
                current_generation_number=best_persistable_champion.generation_number,
            ):
                best_persistable_champion = candidate
                champion_tracking_updated = True

        if champion_tracking_updated:
            generation_lines.append("Best persistable champion updated -> yes")
            generation_lines.append(f"Best persistable champion type -> {champion_type}")
            generation_lines.append(
                "Best persistable champion snapshot -> "
                f"generation={generation_number} | "
                f"validation_selection={best_validation_evaluation.selection_score:.4f} | "
                f"validation_profit={best_validation_evaluation.median_profit:.4f} | "
                f"validation_drawdown={best_validation_evaluation.median_drawdown:.4f} | "
                f"selection_gap={selection_gap:.4f}"
            )
        elif should_persist_champion(champion_type):
            generation_lines.append("Best persistable champion updated -> no")
            generation_lines.append(f"Best persistable champion type -> {champion_type}")
        else:
            generation_lines.append("Best persistable champion updated -> no")
            generation_lines.append(f"Best persistable champion type -> {champion_type}")

        append_lines(log_file_path, generation_lines)

        print(
            f"Generation {generation_number} | "
            f"evolution_best={evolution_best:.4f} | "
            f"train_profit={best_train_evaluation.median_profit:.4f} | "
            f"validation_selection={best_validation_evaluation.selection_score:.4f} | "
            f"validation_profit={best_validation_evaluation.median_profit:.4f} | "
            f"validation_dispersion={best_validation_evaluation.dispersion:.4f} | "
            f"selection_gap={selection_gap:.4f} | "
            f"champion_type={champion_type} | "
            f"profit_gap={profit_gap:.4f} | "
            f"best_persistable_updated={champion_tracking_updated} | "
            f"time={generation_duration:.2f}s | "
            f"log={log_file_path.name}"
        )

        if progress_snapshot_path is not None:
            write_progress_snapshot(
                progress_snapshot_path,
                config_name=config_name,
                mutation_seed=config.mutation_seed,
                current_generation=generation_number,
                total_generations=config.generations_planned,
                validation_selection=best_validation_evaluation.selection_score,
                elapsed_seconds=time.perf_counter() - run_start_time,
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

    persisted_champion_generation: int | None = None
    persisted_champion_type: str | None = None
    external_validation_status = "not_run"

    if best_persistable_champion is not None:
        effective_config_snapshot = (
            dict(config_json_snapshot)
            if config_json_snapshot is not None
            else json.loads(config_path.read_text(encoding="utf-8"))
        )
        champion_metrics = build_champion_metrics(
            train_evaluation=best_persistable_champion.train_evaluation,
            validation_evaluation=best_persistable_champion.validation_evaluation,
            train_dataset_paths=best_persistable_champion.train_dataset_paths,
            validation_dataset_paths=best_persistable_champion.validation_dataset_paths,
            all_train_dataset_paths=best_persistable_champion.all_train_dataset_paths,
            config_name=best_persistable_champion.config_name,
            context_name=best_persistable_champion.context_name,
            dataset_root=best_persistable_champion.dataset_root,
        )
        persisted_champion_generation = best_persistable_champion.generation_number
        persisted_champion_type = best_persistable_champion.champion_type

        if skip_external_validation:
            external_validation_status = "skipped_by_flag"
            warning_lines = [
                "",
                "External validation",
                "WARNING: external validation skipped -> flag enabled",
            ]
            append_lines(log_file_path, warning_lines)
            print("WARNING: external validation skipped -> flag enabled")
        elif not external_validation_dir.exists():
            external_validation_status = "skipped_missing_dir"
            warning_lines = [
                "",
                "External validation",
                (
                    "WARNING: external validation skipped -> directory not found: "
                    f"{external_validation_dir}"
                ),
            ]
            append_lines(log_file_path, warning_lines)
            print(
                "WARNING: external validation skipped -> "
                f"directory not found: {external_validation_dir}"
            )
        else:
            # TODO: External validation datasets should remain disjoint from
            # train/validation pools to avoid leakage across evaluation layers.
            external_dataset_paths = resolve_external_validation_dataset_paths(
                external_validation_dir
            )
            if not external_dataset_paths:
                external_validation_status = "skipped_no_datasets"
                warning_lines = [
                    "",
                    "External validation",
                    (
                        "WARNING: external validation skipped -> no datasets found under "
                        f"{external_validation_dir}"
                    ),
                ]
                append_lines(log_file_path, warning_lines)
                print(
                    "WARNING: external validation skipped -> "
                    f"no datasets found under {external_validation_dir}"
                )
            else:
                external_validation_status = "completed"
                start_lines = [
                    "",
                    "External validation",
                    "External validation started",
                    f"External validation directory: {external_validation_dir}",
                    (
                        "External validation dataset count: "
                        f"{len(external_dataset_paths)}"
                    ),
                    (
                        "External validation datasets: "
                        f"{format_dataset_list(external_dataset_paths, external_validation_dir)}"
                    ),
                ]
                append_lines(log_file_path, start_lines)
                print(
                    "External validation started -> "
                    f"datasets={len(external_dataset_paths)}"
                )

                external_validation_evaluation = run_external_validation(
                    agent=Agent.create(best_persistable_champion.genome),
                    external_dataset_paths=external_dataset_paths,
                    cost_penalty_weight=config.cost_penalty_weight,
                    trade_count_penalty_weight=config.trade_count_penalty_weight,
                    trade_cost_rate=config.trade_cost_rate,
                    regime_filter_enabled=config.regime_filter_enabled,
                    min_trend_long_for_entry=config.min_trend_long_for_entry,
                    min_breakout_for_entry=config.min_breakout_for_entry,
                    max_realized_volatility_for_entry=config.max_realized_volatility_for_entry,
                )
                external_validation_metrics = build_external_validation_metrics(
                    evaluation=external_validation_evaluation,
                    dataset_paths=external_dataset_paths,
                    dataset_root=external_validation_dir,
                )
                champion_metrics.update(external_validation_metrics)

                completion_lines = [
                    format_evaluation(
                        "External validation",
                        external_validation_evaluation,
                    ),
                    "External validation completed",
                ]
                completion_lines.extend(
                    build_dataset_breakdown_lines(
                        external_dataset_paths,
                        external_validation_evaluation,
                        "External validation",
                        external_validation_dir,
                    )
                )
                if external_validation_evaluation.violations:
                    completion_lines.append(
                        "External validation violations -> "
                        f"{', '.join(external_validation_evaluation.violations)}"
                    )
                append_lines(log_file_path, completion_lines)
                print(
                    "External validation completed -> "
                    f"selection={external_validation_evaluation.selection_score:.4f} | "
                    f"profit={external_validation_evaluation.median_profit:.4f} | "
                    f"drawdown={external_validation_evaluation.median_drawdown:.4f}"
                )

        if run_execution_id is not None:
            persistence_store = PersistenceStore(persistence_db_path)
            persistence_store.initialize()
            persistence_store.save_champion(
                champion_uid=str(uuid.uuid4()),
                run_execution_id=run_execution_id,
                run_id=run_id,
                config_name=best_persistable_champion.config_name,
                config_json_snapshot=effective_config_snapshot,
                generation_number=best_persistable_champion.generation_number,
                mutation_seed=best_persistable_champion.mutation_seed,
                champion_type=best_persistable_champion.champion_type,
                genome_json_snapshot=best_persistable_champion.genome.to_dict(),
                dataset_catalog_id=config.dataset_catalog_id,
                dataset_signature=champion_metrics["dataset_signature"],
                train_metrics_json=serialize_agent_evaluation(
                    best_persistable_champion.train_evaluation
                ),
                validation_metrics_json=serialize_agent_evaluation(
                    best_persistable_champion.validation_evaluation
                ),
                champion_metrics_json=champion_metrics,
                logic_version=CURRENT_LOGIC_VERSION,
            )

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
        f"Champion persisted at end -> {'yes' if best_persistable_champion is not None else 'no'}",
        f"External validation status: {external_validation_status}",
        f"Total run time: {total_run_duration:.2f}s",
        f"Average generation time: {average_generation_duration:.2f}s",
    ]

    if best_persistable_champion is not None and persisted_champion_generation is not None:
        summary_lines.extend(
            [
                f"Persisted champion generation: {persisted_champion_generation}",
                f"Persisted champion type: {persisted_champion_type}",
                (
                    "Persisted champion context -> "
                    f"config_name={best_persistable_champion.config_name} | "
                    f"context_name={best_persistable_champion.context_name or 'none'} | "
                    f"dataset_root={best_persistable_champion.dataset_root}"
                ),
            ]
        )

    append_lines(log_file_path, summary_lines)

    print(f"Total run time: {total_run_duration:.2f}s")
    print(f"Average generation time: {average_generation_duration:.2f}s")
    if best_persistable_champion is not None and persisted_champion_generation is not None:
        print(
            "Persisted champion -> "
            f"generation={persisted_champion_generation} | "
            f"type={persisted_champion_type}"
        )
    else:
        print("Persisted champion -> none")
    print(f"Detailed run log saved to {log_file_path}")

    if progress_snapshot_path is not None:
        write_progress_snapshot(
            progress_snapshot_path,
            config_name=config_name,
            mutation_seed=config.mutation_seed,
            current_generation=config.generations_planned,
            total_generations=config.generations_planned,
            validation_selection=final_validation_selection_score,
            elapsed_seconds=total_run_duration,
        )

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
        config_path=config_path,
    )

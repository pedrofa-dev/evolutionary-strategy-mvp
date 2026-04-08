from __future__ import annotations

import json
import sqlite3
import shutil
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

from evo_system.domain.run_config import RunConfig
from evo_system.experimental_space.identity import (
    build_experimental_space_snapshot_from_config_snapshot,
)
from evo_system.orchestration.config_loader import load_run_config
from evo_system.storage import DEFAULT_PERSISTENCE_DB_PATH
from evo_system.storage.persistence_store import MULTISEED_RUNS_JSON_COLUMNS


REPO_ROOT = Path(__file__).resolve().parents[3]
RUN_CONFIGS_DIR = REPO_ROOT / "configs" / "runs"


@dataclass(frozen=True)
class ConfigRecentUsageSummary:
    campaign_usage_count: int
    latest_campaign_id: str | None
    latest_campaign_started_at: str | None
    latest_campaign_status: str | None
    appears_in_persisted_executions: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "campaign_usage_count": self.campaign_usage_count,
            "latest_campaign_id": self.latest_campaign_id,
            "latest_campaign_started_at": self.latest_campaign_started_at,
            "latest_campaign_status": self.latest_campaign_status,
            "appears_in_persisted_executions": self.appears_in_persisted_executions,
        }


@dataclass(frozen=True)
class RunConfigBrowserSummary:
    config_name: str
    config_path: str
    dataset_catalog_id: str
    signal_pack_name: str
    genome_schema_name: str
    decision_policy_name: str
    mutation_profile_name: str
    market_mode_name: str
    leverage: float
    seed_mode: str
    seed_start: int | None
    seed_count: int | None
    explicit_seeds: tuple[int, ...]
    seed_summary: str
    generations_planned: int
    recent_usage: ConfigRecentUsageSummary

    def to_dict(self) -> dict[str, Any]:
        return {
            "config_name": self.config_name,
            "config_path": self.config_path,
            "dataset_catalog_id": self.dataset_catalog_id,
            "signal_pack_name": self.signal_pack_name,
            "genome_schema_name": self.genome_schema_name,
            "decision_policy_name": self.decision_policy_name,
            "mutation_profile_name": self.mutation_profile_name,
            "market_mode_name": self.market_mode_name,
            "leverage": self.leverage,
            "seed_mode": self.seed_mode,
            "seed_start": self.seed_start,
            "seed_count": self.seed_count,
            "explicit_seeds": list(self.explicit_seeds),
            "seed_summary": self.seed_summary,
            "generations_planned": self.generations_planned,
            "recent_usage": self.recent_usage.to_dict(),
        }


@dataclass(frozen=True)
class ConfigIdentitySection:
    config_name: str
    config_path: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "config_name": self.config_name,
            "config_path": self.config_path,
        }


@dataclass(frozen=True)
class ConfigResearchStackSection:
    dataset_catalog_id: str
    signal_pack_name: str
    genome_schema_name: str
    decision_policy_name: str
    mutation_profile_name: str
    market_mode_name: str
    leverage: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset_catalog_id": self.dataset_catalog_id,
            "signal_pack_name": self.signal_pack_name,
            "genome_schema_name": self.genome_schema_name,
            "decision_policy_name": self.decision_policy_name,
            "mutation_profile_name": self.mutation_profile_name,
            "market_mode_name": self.market_mode_name,
            "leverage": self.leverage,
        }


@dataclass(frozen=True)
class ConfigEvolutionBudgetSection:
    mutation_seed: int
    population_size: int
    target_population_size: int
    survivors_count: int
    generations_planned: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "mutation_seed": self.mutation_seed,
            "population_size": self.population_size,
            "target_population_size": self.target_population_size,
            "survivors_count": self.survivors_count,
            "generations_planned": self.generations_planned,
        }


@dataclass(frozen=True)
class ConfigSeedPlanSection:
    mode: str
    seed_start: int | None
    seed_count: int | None
    explicit_seeds: tuple[int, ...]
    summary: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "seed_start": self.seed_start,
            "seed_count": self.seed_count,
            "explicit_seeds": list(self.explicit_seeds),
            "summary": self.summary,
        }


@dataclass(frozen=True)
class ConfigEvaluationTradingSection:
    trade_cost_rate: float
    cost_penalty_weight: float
    trade_count_penalty_weight: float
    entry_score_margin: float
    min_bars_between_entries: int
    entry_confirmation_bars: int
    regime_filter_enabled: bool
    min_trend_long_for_entry: float
    min_breakout_for_entry: float
    max_realized_volatility_for_entry: float | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "trade_cost_rate": self.trade_cost_rate,
            "cost_penalty_weight": self.cost_penalty_weight,
            "trade_count_penalty_weight": self.trade_count_penalty_weight,
            "entry_score_margin": self.entry_score_margin,
            "min_bars_between_entries": self.min_bars_between_entries,
            "entry_confirmation_bars": self.entry_confirmation_bars,
            "regime_filter_enabled": self.regime_filter_enabled,
            "min_trend_long_for_entry": self.min_trend_long_for_entry,
            "min_breakout_for_entry": self.min_breakout_for_entry,
            "max_realized_volatility_for_entry": self.max_realized_volatility_for_entry,
        }


@dataclass(frozen=True)
class ConfigAdvancedOverridesSection:
    mutation_profile: dict[str, Any]
    entry_trigger: dict[str, Any]
    exit_policy: dict[str, Any]
    trade_control: dict[str, Any]
    entry_trigger_constraints: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "mutation_profile": dict(self.mutation_profile),
            "entry_trigger": dict(self.entry_trigger),
            "exit_policy": dict(self.exit_policy),
            "trade_control": dict(self.trade_control),
            "entry_trigger_constraints": dict(self.entry_trigger_constraints),
        }


@dataclass(frozen=True)
class RunConfigEditorView:
    identity: ConfigIdentitySection
    research_stack: ConfigResearchStackSection
    evolution_budget: ConfigEvolutionBudgetSection
    seed_plan: ConfigSeedPlanSection
    evaluation_trading: ConfigEvaluationTradingSection
    advanced_overrides: ConfigAdvancedOverridesSection
    recent_usage: ConfigRecentUsageSummary

    def to_dict(self) -> dict[str, Any]:
        return {
            "identity": self.identity.to_dict(),
            "research_stack": self.research_stack.to_dict(),
            "evolution_budget": self.evolution_budget.to_dict(),
            "seed_plan": self.seed_plan.to_dict(),
            "evaluation_trading": self.evaluation_trading.to_dict(),
            "advanced_overrides": self.advanced_overrides.to_dict(),
            "recent_usage": self.recent_usage.to_dict(),
        }


@dataclass(frozen=True)
class RunConfigFileOperationResult:
    config_name: str
    config_path: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "config_name": self.config_name,
            "config_path": self.config_path,
        }


@dataclass(frozen=True)
class _RecentUsageAccumulator:
    campaign_usage_count: int = 0
    latest_campaign_id: str | None = None
    latest_campaign_started_at: str | None = None
    latest_campaign_status: str | None = None
    appears_in_persisted_executions: bool = False

    def to_summary(self) -> ConfigRecentUsageSummary:
        return ConfigRecentUsageSummary(
            campaign_usage_count=self.campaign_usage_count,
            latest_campaign_id=self.latest_campaign_id,
            latest_campaign_started_at=self.latest_campaign_started_at,
            latest_campaign_status=self.latest_campaign_status,
            appears_in_persisted_executions=self.appears_in_persisted_executions,
        )


class RunConfigBrowserApplicationService:
    """Read/write application layer for canonical run config files.

    This layer is intentionally narrow:
    - it reads canonical config JSON files under configs/runs/
    - it normalizes them into explicit editor DTOs
    - it performs safe filesystem operations such as duplicate/rename
    - it derives lightweight recent usage from existing persisted campaign data
    """

    def __init__(
        self,
        *,
        repo_root: Path = REPO_ROOT,
        run_configs_dir: Path = RUN_CONFIGS_DIR,
        database_path: str | Path | None = None,
    ) -> None:
        self.repo_root = repo_root
        self.run_configs_dir = run_configs_dir
        self.database_path = (
            Path(database_path)
            if database_path is not None
            else repo_root / DEFAULT_PERSISTENCE_DB_PATH
        )

    def list_configs(self) -> tuple[RunConfigBrowserSummary, ...]:
        usage_index = self._build_recent_usage_index()
        summaries = [
            self._build_browser_summary(path, usage_index=usage_index)
            for path in sorted(self.run_configs_dir.glob("*.json"))
        ]
        return tuple(summaries)

    def get_config(self, config_name: str) -> RunConfigEditorView:
        path = self._resolve_config_path(config_name)
        usage_index = self._build_recent_usage_index()
        return self._build_editor_view(path, usage_index=usage_index)

    def duplicate_config(
        self,
        *,
        source_config_name: str,
        new_config_name: str,
    ) -> RunConfigFileOperationResult:
        source_path = self._resolve_config_path(source_config_name)
        target_name = _normalize_config_name(new_config_name)
        target_path = self.run_configs_dir / target_name
        if target_path.exists():
            raise ValueError(
                "Run config name already exists. Choose a different config name instead of overwriting it."
            )
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target_path)
        return RunConfigFileOperationResult(
            config_name=target_path.name,
            config_path=self._to_repo_relative_path(target_path),
        )

    def rename_config(
        self,
        *,
        source_config_name: str,
        new_config_name: str,
    ) -> RunConfigFileOperationResult:
        source_path = self._resolve_config_path(source_config_name)
        target_name = _normalize_config_name(new_config_name)
        target_path = self.run_configs_dir / target_name
        if source_path == target_path:
            return RunConfigFileOperationResult(
                config_name=source_path.name,
                config_path=self._to_repo_relative_path(source_path),
            )
        if target_path.exists():
            raise ValueError(
                "Run config name already exists. Choose a different config name instead of overwriting it."
            )
        source_path.rename(target_path)
        return RunConfigFileOperationResult(
            config_name=target_path.name,
            config_path=self._to_repo_relative_path(target_path),
        )

    def save_config(
        self,
        *,
        source_config_name: str,
        config_payload: dict[str, Any],
    ) -> RunConfigEditorView:
        source_path = self._resolve_config_path(source_config_name)
        target_name = self._extract_target_config_name(config_payload)
        if target_name != source_path.name:
            raise ValueError(
                "Config save cannot rename files implicitly. "
                "Use rename or save-as-new instead."
            )
        self._write_validated_config(target_path=source_path, payload=config_payload)
        usage_index = self._build_recent_usage_index()
        return self._build_editor_view(source_path, usage_index=usage_index)

    def save_config_as_new(
        self,
        *,
        config_payload: dict[str, Any],
    ) -> RunConfigEditorView:
        target_name = self._extract_target_config_name(config_payload)
        target_path = self.run_configs_dir / target_name
        if target_path.exists():
            raise ValueError(
                "Run config name already exists. Choose a different config name instead of overwriting it."
            )
        self._write_validated_config(target_path=target_path, payload=config_payload)
        usage_index = self._build_recent_usage_index()
        return self._build_editor_view(target_path, usage_index=usage_index)

    def _build_browser_summary(
        self,
        path: Path,
        *,
        usage_index: dict[str, ConfigRecentUsageSummary],
    ) -> RunConfigBrowserSummary:
        raw_payload = self._load_raw_config_payload(path)
        seed_mode, explicit_seeds, seed_start, seed_count, seed_summary = (
            _build_seed_plan_from_payload(raw_payload)
        )
        snapshot = build_experimental_space_snapshot_from_config_snapshot(raw_payload)
        return RunConfigBrowserSummary(
            config_name=path.name,
            config_path=self._to_repo_relative_path(path),
            dataset_catalog_id=str(raw_payload["dataset_catalog_id"]),
            signal_pack_name=snapshot.signal_pack_name,
            genome_schema_name=snapshot.genome_schema_name,
            decision_policy_name=snapshot.decision_policy_name,
            mutation_profile_name=snapshot.mutation_profile_name,
            market_mode_name=snapshot.market_mode_name,
            leverage=float(snapshot.leverage),
            seed_mode=seed_mode,
            seed_start=seed_start,
            seed_count=seed_count,
            explicit_seeds=explicit_seeds,
            seed_summary=seed_summary,
            generations_planned=int(raw_payload["generations_planned"]),
            recent_usage=usage_index.get(
                path.name,
                ConfigRecentUsageSummary(0, None, None, None, False),
            ),
        )

    def _build_editor_view(
        self,
        path: Path,
        *,
        usage_index: dict[str, ConfigRecentUsageSummary],
    ) -> RunConfigEditorView:
        config = self._load_run_config(path)
        config_dict = config.to_dict()
        seed_mode, explicit_seeds, seed_start, seed_count, seed_summary = (
            _build_seed_plan_from_run_config(config)
        )
        return RunConfigEditorView(
            identity=ConfigIdentitySection(
                config_name=path.name,
                config_path=self._to_repo_relative_path(path),
            ),
            research_stack=ConfigResearchStackSection(
                dataset_catalog_id=config.dataset_catalog_id,
                signal_pack_name=config.signal_pack_name,
                genome_schema_name=config.genome_schema_name,
                decision_policy_name=config.decision_policy_name,
                mutation_profile_name=config.mutation_profile_name,
                market_mode_name=config.market_mode_name,
                leverage=config.leverage,
            ),
            evolution_budget=ConfigEvolutionBudgetSection(
                mutation_seed=config.mutation_seed,
                population_size=config.population_size,
                target_population_size=config.target_population_size,
                survivors_count=config.survivors_count,
                generations_planned=config.generations_planned,
            ),
            seed_plan=ConfigSeedPlanSection(
                mode=seed_mode,
                seed_start=seed_start,
                seed_count=seed_count,
                explicit_seeds=explicit_seeds,
                summary=seed_summary,
            ),
            evaluation_trading=ConfigEvaluationTradingSection(
                trade_cost_rate=config.trade_cost_rate,
                cost_penalty_weight=config.cost_penalty_weight,
                trade_count_penalty_weight=config.trade_count_penalty_weight,
                entry_score_margin=config.entry_score_margin,
                min_bars_between_entries=config.min_bars_between_entries,
                entry_confirmation_bars=config.entry_confirmation_bars,
                regime_filter_enabled=config.regime_filter_enabled,
                min_trend_long_for_entry=config.min_trend_long_for_entry,
                min_breakout_for_entry=config.min_breakout_for_entry,
                max_realized_volatility_for_entry=config.max_realized_volatility_for_entry,
            ),
            advanced_overrides=ConfigAdvancedOverridesSection(
                mutation_profile=dict(config_dict["mutation_profile"]),
                entry_trigger=dict(config.entry_trigger_overrides or {}),
                exit_policy=dict(config.exit_policy_overrides or {}),
                trade_control=dict(config.trade_control_overrides or {}),
                entry_trigger_constraints=dict(config.entry_trigger_constraints or {}),
            ),
            recent_usage=usage_index.get(
                path.name,
                ConfigRecentUsageSummary(0, None, None, None, False),
            ),
        )

    def _load_raw_config_payload(self, path: Path) -> dict[str, Any]:
        return json.loads(path.read_text(encoding="utf-8"))

    def _load_run_config(self, path: Path) -> RunConfig:
        return load_run_config(str(path))

    def _extract_target_config_name(self, config_payload: dict[str, Any]) -> str:
        try:
            identity = config_payload["identity"]
            config_name = identity["config_name"]
        except (TypeError, KeyError) as exc:
            raise ValueError("config.identity.config_name is required") from exc
        return _normalize_config_name(str(config_name))

    def _write_validated_config(
        self,
        *,
        target_path: Path,
        payload: dict[str, Any],
    ) -> None:
        candidate_payload = _build_canonical_config_payload_from_editor_payload(payload)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = target_path.with_name(f".{target_path.name}.tmp")
        try:
            temp_path.write_text(
                json.dumps(candidate_payload, indent=2) + "\n",
                encoding="utf-8",
            )
            load_run_config(str(temp_path))
            temp_path.replace(target_path)
        finally:
            if temp_path.exists():
                temp_path.unlink()

    def _resolve_config_path(self, config_name: str) -> Path:
        normalized = _normalize_config_name(config_name)
        path = self.run_configs_dir / normalized
        if not path.exists():
            raise ValueError(f"Unknown run config: {normalized}")
        return path

    def _to_repo_relative_path(self, path: Path) -> str:
        return path.relative_to(self.repo_root).as_posix()

    @contextmanager
    def _connect_readonly(self) -> Iterator[sqlite3.Connection]:
        if not self.database_path.exists():
            raise FileNotFoundError(f"Database not found: {self.database_path}")
        connection = sqlite3.connect(
            f"file:{self.database_path.resolve().as_posix()}?mode=ro",
            uri=True,
        )
        connection.row_factory = sqlite3.Row
        try:
            yield connection
        finally:
            connection.close()

    def _build_recent_usage_index(self) -> dict[str, ConfigRecentUsageSummary]:
        if not self.database_path.exists():
            return {}

        usage_map: dict[str, _RecentUsageAccumulator] = {}
        with self._connect_readonly() as connection:
            campaign_rows = connection.execute(
                """
                SELECT
                    multiseed_run_uid,
                    started_at,
                    status,
                    configs_dir_snapshot_json
                FROM multiseed_runs
                ORDER BY started_at DESC, id DESC
                """
            ).fetchall()
            execution_rows = connection.execute(
                """
                SELECT DISTINCT config_name
                FROM run_executions
                """
            ).fetchall()

        for row in campaign_rows:
            campaign_payload = _row_to_dict(row, MULTISEED_RUNS_JSON_COLUMNS)
            config_names = _extract_config_names(
                campaign_payload.get("configs_dir_snapshot_json") or {}
            )
            for config_name in config_names:
                current = usage_map.get(config_name, _RecentUsageAccumulator())
                usage_map[config_name] = _RecentUsageAccumulator(
                    campaign_usage_count=current.campaign_usage_count + 1,
                    latest_campaign_id=(
                        current.latest_campaign_id
                        if current.latest_campaign_id is not None
                        else str(campaign_payload["multiseed_run_uid"])
                    ),
                    latest_campaign_started_at=(
                        current.latest_campaign_started_at
                        if current.latest_campaign_started_at is not None
                        else campaign_payload.get("started_at")
                    ),
                    latest_campaign_status=(
                        current.latest_campaign_status
                        if current.latest_campaign_status is not None
                        else campaign_payload.get("status")
                    ),
                    appears_in_persisted_executions=current.appears_in_persisted_executions,
                )

        for row in execution_rows:
            config_name = str(row["config_name"])
            current = usage_map.get(config_name, _RecentUsageAccumulator())
            usage_map[config_name] = _RecentUsageAccumulator(
                campaign_usage_count=current.campaign_usage_count,
                latest_campaign_id=current.latest_campaign_id,
                latest_campaign_started_at=current.latest_campaign_started_at,
                latest_campaign_status=current.latest_campaign_status,
                appears_in_persisted_executions=True,
            )

        return {
            config_name: accumulator.to_summary()
            for config_name, accumulator in usage_map.items()
        }


def _row_to_dict(row: sqlite3.Row, json_columns: set[str]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for key in row.keys():
        value = row[key]
        payload[key] = json.loads(value) if key in json_columns and value is not None else value
    return payload


def _extract_config_names(configs_dir_snapshot: dict[str, Any]) -> list[str]:
    configs = configs_dir_snapshot.get("configs") or []
    names: list[str] = []
    for item in configs:
        if isinstance(item, str):
            names.append(item)
        elif isinstance(item, dict):
            config_name = item.get("config_name")
            if isinstance(config_name, str):
                names.append(config_name)
    return names


def _normalize_config_name(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError("config_name is required")
    if any(separator in stripped for separator in ("/", "\\")):
        raise ValueError("config_name must be a simple file name, not a path")
    if not stripped.endswith(".json"):
        stripped = f"{stripped}.json"
    return stripped


def _build_canonical_config_payload_from_editor_payload(
    payload: dict[str, Any],
) -> dict[str, Any]:
    try:
        research_stack = payload["research_stack"]
        evolution_budget = payload["evolution_budget"]
        seed_plan = payload["seed_plan"]
        evaluation_trading = payload["evaluation_trading"]
        advanced_overrides = payload["advanced_overrides"]
    except (TypeError, KeyError) as exc:
        raise ValueError(
            "Config payload must include research_stack, evolution_budget, seed_plan, "
            "evaluation_trading, and advanced_overrides sections."
        ) from exc

    candidate_payload: dict[str, Any] = {
        "dataset_catalog_id": str(research_stack["dataset_catalog_id"]).strip(),
        "signal_pack_name": str(research_stack["signal_pack_name"]).strip(),
        "genome_schema_name": str(research_stack["genome_schema_name"]).strip(),
        "decision_policy_name": str(research_stack["decision_policy_name"]).strip(),
        "mutation_profile_name": str(research_stack["mutation_profile_name"]).strip(),
        "market_mode_name": str(research_stack["market_mode_name"]).strip(),
        "leverage": float(research_stack["leverage"]),
        "mutation_seed": int(evolution_budget["mutation_seed"]),
        "population_size": int(evolution_budget["population_size"]),
        "target_population_size": int(evolution_budget["target_population_size"]),
        "survivors_count": int(evolution_budget["survivors_count"]),
        "generations_planned": int(evolution_budget["generations_planned"]),
        "trade_cost_rate": float(evaluation_trading["trade_cost_rate"]),
        "cost_penalty_weight": float(evaluation_trading["cost_penalty_weight"]),
        "trade_count_penalty_weight": float(
            evaluation_trading["trade_count_penalty_weight"]
        ),
        "entry_score_margin": float(evaluation_trading["entry_score_margin"]),
        "min_bars_between_entries": int(
            evaluation_trading["min_bars_between_entries"]
        ),
        "entry_confirmation_bars": int(
            evaluation_trading["entry_confirmation_bars"]
        ),
        "regime_filter_enabled": bool(
            evaluation_trading["regime_filter_enabled"]
        ),
        "min_trend_long_for_entry": float(
            evaluation_trading["min_trend_long_for_entry"]
        ),
        "min_breakout_for_entry": float(
            evaluation_trading["min_breakout_for_entry"]
        ),
        "max_realized_volatility_for_entry": (
            None
            if evaluation_trading.get("max_realized_volatility_for_entry") is None
            else float(evaluation_trading["max_realized_volatility_for_entry"])
        ),
        "mutation_profile": dict(advanced_overrides["mutation_profile"]),
        "entry_trigger": dict(advanced_overrides["entry_trigger"]),
        "exit_policy": dict(advanced_overrides["exit_policy"]),
        "trade_control": dict(advanced_overrides["trade_control"]),
        "entry_trigger_constraints": dict(
            advanced_overrides["entry_trigger_constraints"]
        ),
    }

    seed_mode = str(seed_plan.get("mode") or "runtime_default").strip()
    if seed_mode == "explicit":
        explicit_seeds = seed_plan.get("explicit_seeds")
        if not isinstance(explicit_seeds, list) or not explicit_seeds:
            raise ValueError("Explicit seed mode requires at least one explicit seed.")
        candidate_payload["seeds"] = [int(seed) for seed in explicit_seeds]
    elif seed_mode == "range":
        if seed_plan.get("seed_start") is None or seed_plan.get("seed_count") is None:
            raise ValueError("Range seed mode requires seed_start and seed_count.")
        candidate_payload["seed_start"] = int(seed_plan["seed_start"])
        candidate_payload["seed_count"] = int(seed_plan["seed_count"])
    elif seed_mode != "runtime_default":
        raise ValueError(f"Unsupported seed mode: {seed_mode}")

    return candidate_payload


def _build_seed_plan_from_payload(
    payload: dict[str, Any],
) -> tuple[str, tuple[int, ...], int | None, int | None, str]:
    explicit_seeds = tuple(int(seed) for seed in payload.get("seeds", []) or [])
    if explicit_seeds:
        summary = ", ".join(str(seed) for seed in explicit_seeds)
        return "explicit", explicit_seeds, None, None, summary

    seed_start = int(payload["seed_start"]) if payload.get("seed_start") is not None else None
    seed_count = int(payload["seed_count"]) if payload.get("seed_count") is not None else None
    if seed_start is not None and seed_count is not None:
        end_seed = seed_start + seed_count - 1
        return "range", (), seed_start, seed_count, f"{seed_start}-{end_seed} ({seed_count} seeds)"

    return "runtime_default", (), None, None, "Runtime default seed plan"


def _build_seed_plan_from_run_config(
    config: RunConfig,
) -> tuple[str, tuple[int, ...], int | None, int | None, str]:
    if config.seeds is not None:
        explicit_seeds = tuple(int(seed) for seed in config.seeds)
        summary = ", ".join(str(seed) for seed in explicit_seeds)
        return "explicit", explicit_seeds, None, None, summary

    if config.seed_start is not None and config.seed_count is not None:
        end_seed = config.seed_start + config.seed_count - 1
        return (
            "range",
            (),
            config.seed_start,
            config.seed_count,
            f"{config.seed_start}-{end_seed} ({config.seed_count} seeds)",
        )

    return "runtime_default", (), None, None, "Runtime default seed plan"

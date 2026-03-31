import json
from pathlib import Path

import pytest

from evo_system.experimentation.cli import build_parser
from evo_system.experimentation.dataset_roots import (
    DEFAULT_DATASET_ROOT,
    format_effective_dataset_roots,
    resolve_dataset_root,
)
from evo_system.experimentation.historical_run import execute_historical_run
from evo_system.experimentation.multiseed_run import (
    MULTISEED_RUN_SUMMARY_NAME,
    MultiseedExecutionOutcome,
    MultiseedJob,
    build_default_multiseed_seeds,
    build_multiseed_jobs,
    calculate_effective_parallel_workers,
    execute_multiseed_job_sequential,
    execute_multiseed_runs,
    execute_multiseed_runs_with_failures,
    format_parallel_progress,
    format_seed_plan,
    resolve_config_seeds,
    resolve_seed_map,
    run_multiseed_experiment,
)
from evo_system.experimentation.parallel_progress import format_active_job_progress
from evo_system.experimentation.post_multiseed_analysis import (
    CHAMPIONS_ANALYSIS_DIRNAME,
    MULTISEED_CHAMPIONS_SUMMARY_NAME,
    MULTISEED_QUICK_SUMMARY_NAME,
    POST_MULTISEED_VALIDATION_DIRNAME,
)
from evo_system.experimentation.presets import (
    apply_preset_to_seeds,
    get_available_preset_names,
    get_preset_by_name,
)


def write_config(
    path: Path,
    *,
    extra_fields: dict | None = None,
) -> None:
    payload = {
        "mutation_seed": 42,
        "population_size": 12,
        "target_population_size": 12,
        "survivors_count": 4,
        "generations_planned": 25,
        "dataset_catalog_id": "core_1h_spot",
    }
    if extra_fields:
        payload.update(extra_fields)
    path.write_text(json.dumps(payload), encoding="utf-8")


def build_summary(config_path: Path, *, seed: int, run_id: str):
    return type(
        "Summary",
        (),
        {
            "config_name": config_path.name,
            "run_id": run_id,
            "log_file_path": config_path.with_suffix(".txt"),
            "mutation_seed": seed,
            "best_train_selection_score": 1.1,
            "final_validation_selection_score": 0.9,
            "final_validation_profit": 0.02,
            "final_validation_drawdown": 0.01,
            "final_validation_trades": 15.0,
            "best_genome_repr": "genome",
            "generation_of_best": 5,
            "train_validation_selection_gap": 0.1,
            "train_validation_profit_gap": 0.01,
            "config_path": config_path,
        },
    )()


def test_cli_exposes_execution_arguments_at_top_level() -> None:
    parser = build_parser()

    args = parser.parse_args(
        ["--configs-dir", "configs/runs", "--parallel-workers", "4"]
    )

    assert args.configs_dir == Path("configs/runs")
    assert args.parallel_workers == 4


def test_cli_parses_multiseed_post_analysis_arguments() -> None:
    parser = build_parser()

    args = parser.parse_args(
        [
            "--configs-dir",
            "configs/runs",
            "--external-validation-dir",
            "data/datasets/external_validation",
            "--audit-dir",
            "data/datasets/audit",
            "--skip-post-multiseed-analysis",
        ]
    )

    assert str(args.external_validation_dir).endswith("external_validation")
    assert str(args.audit_dir).endswith("audit")
    assert args.skip_post_multiseed_analysis is True


def test_experiment_presets_include_standard_extended_and_full() -> None:
    assert get_available_preset_names() == [
        "extended",
        "full",
        "quick",
        "screening",
        "standard",
    ]

    standard = get_preset_by_name("standard")
    extended = get_preset_by_name("extended")
    full = get_preset_by_name("full")

    assert standard is not None
    assert extended is not None
    assert full is not None

    assert standard.generations == 25
    assert standard.max_seeds == 6
    assert extended.generations == 35
    assert extended.max_seeds == 10
    assert full.generations == 50
    assert full.max_seeds == 100

    seeds = [101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111]
    assert apply_preset_to_seeds(seeds, standard) == seeds[:6]
    assert apply_preset_to_seeds(seeds, extended) == seeds[:10]
    assert apply_preset_to_seeds(seeds, full) == seeds


def test_manifest_dataset_root_resolution_uses_data_datasets_by_default() -> None:
    assert resolve_dataset_root(DEFAULT_DATASET_ROOT) == DEFAULT_DATASET_ROOT


def test_execute_historical_run_uses_manifest_dataset_root_by_default(
    monkeypatch,
    tmp_path: Path,
) -> None:
    captured_dataset_root: dict[str, Path] = {}

    class StopAfterDatasetLoad(Exception):
        pass

    def fake_load_paths(self, dataset_root: Path, dataset_catalog_id: str):
        captured_dataset_root["value"] = dataset_root
        raise StopAfterDatasetLoad

    monkeypatch.setattr(
        "evo_system.experimentation.historical_run.DatasetPoolLoader.load_paths",
        fake_load_paths,
    )

    config_path = tmp_path / "run_balanced_manifest.json"
    write_config(config_path, extra_fields={"population_size": 18, "target_population_size": 18})

    with pytest.raises(StopAfterDatasetLoad):
        execute_historical_run(config_path=config_path)

    assert captured_dataset_root["value"] == DEFAULT_DATASET_ROOT


def test_build_multiseed_jobs_expands_config_seed_pairs(tmp_path: Path) -> None:
    config_paths = [tmp_path / "a.json", tmp_path / "b.json"]
    seed_map = {
        config_paths[0]: [101, 102],
        config_paths[1]: [101, 102],
    }

    jobs = build_multiseed_jobs(
        seed_map=seed_map,
        output_dir=tmp_path / "out",
        dataset_root=tmp_path / "datasets",
        context_name=None,
        preset_name=None,
    )

    assert len(jobs) == 4
    assert jobs[0].config_path == config_paths[0]
    assert jobs[0].seed == 101
    assert jobs[-1].config_path == config_paths[1]
    assert jobs[-1].seed == 102


def test_effective_parallel_workers_falls_back_when_job_count_is_too_small() -> None:
    assert calculate_effective_parallel_workers(1, 4) == 1
    assert calculate_effective_parallel_workers(3, 8) == 3


def test_format_parallel_progress_is_human_readable() -> None:
    progress_line = format_parallel_progress(
        completed_jobs=3,
        total_jobs=10,
        success_count=2,
        failure_count=1,
        last_label="run_balanced seed=103",
    )

    assert progress_line == "[3/10] completed | success=2 | failed=1 | last=run_balanced seed=103"


def test_format_active_job_progress_is_human_readable() -> None:
    line = format_active_job_progress(
        {
            "config_name": "run_balanced_manifest",
            "mutation_seed": 103,
            "current_generation": 17,
            "total_generations": 40,
            "validation_selection": 0.84,
            "elapsed_seconds": 591,
        },
        fallback_label="fallback",
    )

    assert (
        line
        == "- run_balanced_manifest seed=103 | gen 17/40 | validation_selection=0.8400 | elapsed=09:51"
    )


def test_execute_multiseed_runs_keeps_sequential_run_output_path(
    monkeypatch,
    tmp_path: Path,
) -> None:
    calls: list[str] = []

    def fake_execute_historical_run(**kwargs):
        calls.append(kwargs["config_name_override"])
        return build_summary(
            tmp_path / kwargs["config_name_override"],
            seed=101,
            run_id=f"run-{kwargs['config_name_override']}-101",
        )

    monkeypatch.setattr(
        "evo_system.experimentation.multiseed_run.execute_historical_run",
        fake_execute_historical_run,
    )

    config_path = tmp_path / "a.json"
    write_config(config_path)

    summaries = execute_multiseed_runs(
        config_paths=[config_path],
        output_dir=tmp_path / "out",
        dataset_root=tmp_path / "datasets",
        context_name=None,
        preset_name=None,
        requested_parallel_workers=1,
    )

    assert calls == ["a.json"] * 6
    assert len(summaries) == 6


def test_execute_multiseed_runs_with_failures_collects_sequential_seed_errors(
    monkeypatch,
    tmp_path: Path,
) -> None:
    calls: list[int] = []

    def fake_execute_historical_run(**kwargs):
        config = json.loads(kwargs["config_path"].read_text(encoding="utf-8"))
        seed = config["mutation_seed"]
        calls.append(seed)
        if seed == 102:
            raise RuntimeError("boom")
        return build_summary(tmp_path / "a.json", seed=seed, run_id=f"run-{seed}")

    monkeypatch.setattr(
        "evo_system.experimentation.multiseed_run.execute_historical_run",
        fake_execute_historical_run,
    )

    config_path = tmp_path / "a.json"
    write_config(config_path, extra_fields={"seeds": [101, 102, 103]})

    outcome = execute_multiseed_runs_with_failures(
        config_paths=[config_path],
        output_dir=tmp_path / "out",
        dataset_root=tmp_path / "datasets",
        context_name=None,
        preset_name=None,
        requested_parallel_workers=1,
    )

    assert calls == [101, 102, 103]
    assert [summary.run_id for summary in outcome.run_summaries] == ["run-101", "run-103"]
    assert outcome.failures == ["a.json seed 102: boom"]


def test_execute_multiseed_job_sequential_preserves_original_config_path(
    monkeypatch,
    tmp_path: Path,
) -> None:
    original_config_path = tmp_path / "a.json"
    write_config(original_config_path)

    def fake_execute_historical_run(**kwargs):
        return build_summary(kwargs["config_path"], seed=101, run_id="run-001")

    monkeypatch.setattr(
        "evo_system.experimentation.multiseed_run.execute_historical_run",
        fake_execute_historical_run,
    )

    summary = execute_multiseed_job_sequential(
        MultiseedJob(
            config_path=original_config_path,
            seed=101,
            output_dir=tmp_path / "out",
            dataset_root=tmp_path / "datasets",
            context_name=None,
            preset_name=None,
            progress_snapshot_path=tmp_path / "progress.json",
        )
    )

    assert summary.config_path == original_config_path


def test_resolve_config_seeds_uses_explicit_seeds_when_present(tmp_path: Path) -> None:
    config_path = tmp_path / "a.json"
    write_config(config_path, extra_fields={"seeds": [201, 202, 203]})

    assert resolve_config_seeds(config_path) == [201, 202, 203]


def test_resolve_config_seeds_uses_seed_range_when_present(tmp_path: Path) -> None:
    config_path = tmp_path / "a.json"
    write_config(config_path, extra_fields={"seed_start": 100, "seed_count": 4})

    assert resolve_config_seeds(config_path) == [100, 101, 102, 103]


def test_resolve_config_seeds_falls_back_to_default_seed_plan(tmp_path: Path) -> None:
    config_path = tmp_path / "a.json"
    write_config(config_path)

    assert resolve_config_seeds(config_path) == build_default_multiseed_seeds()


def test_resolve_seed_map_applies_presets_to_config_defined_seeds(tmp_path: Path) -> None:
    config_path = tmp_path / "a.json"
    write_config(config_path, extra_fields={"seeds": [201, 202, 203, 204, 205, 206, 207]})

    seed_map = resolve_seed_map([config_path], "standard")

    assert seed_map[config_path] == [201, 202, 203, 204, 205, 206]


def test_format_seed_plan_supports_per_config_seed_lists(tmp_path: Path) -> None:
    config_a = tmp_path / "a.json"
    config_b = tmp_path / "b.json"

    formatted = format_seed_plan(
        {
            config_a: [101, 102],
            config_b: [201, 202],
        }
    )

    assert formatted == "a.json: 101, 102 | b.json: 201, 202"


def test_run_multiseed_experiment_reports_effective_manifest_dataset_root(
    monkeypatch,
    capsys,
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "run_balanced_manifest.json"
    write_config(config_path, extra_fields={"population_size": 18, "target_population_size": 18})

    monkeypatch.setattr(
        "evo_system.experimentation.multiseed_run.execute_multiseed_runs_with_failures",
        lambda **kwargs: MultiseedExecutionOutcome(run_summaries=[], failures=[]),
    )
    monkeypatch.setattr(
        "evo_system.experimentation.multiseed_run.create_multiseed_dir",
        lambda: tmp_path / "out",
    )
    monkeypatch.setattr(
        "evo_system.experimentation.multiseed_run.write_multiseed_quick_summary",
        lambda **kwargs: tmp_path / "quick.txt",
    )
    monkeypatch.setattr(
        "evo_system.experimentation.multiseed_run.write_multiseed_summary",
        lambda **kwargs: tmp_path / "summary.txt",
    )
    monkeypatch.setattr(
        "evo_system.experimentation.multiseed_run.run_post_multiseed_analysis",
        lambda **kwargs: type(
            "Result",
            (),
            {
                "summary_path": tmp_path / "summary.txt",
                "quick_summary_path": tmp_path / "quick.txt",
                "champions_summary_path": tmp_path / "champions.txt",
                "champions_analysis_dir": tmp_path / "analysis",
                "external_output_dir": tmp_path / "external",
                "audit_output_dir": tmp_path / "audit",
            },
        )(),
    )

    run_multiseed_experiment(
        configs_dir=tmp_path,
        dataset_root=DEFAULT_DATASET_ROOT,
        preset_name="screening",
        parallel_workers=1,
    )

    captured = capsys.readouterr()
    assert "Dataset root: data\\datasets" in captured.out


def test_run_multiseed_experiment_generates_post_multiseed_artifacts(
    monkeypatch,
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "run_a.json"
    write_config(config_path, extra_fields={"population_size": 18, "target_population_size": 18})

    monkeypatch.setattr(
        "evo_system.experimentation.multiseed_run.execute_multiseed_runs_with_failures",
        lambda **kwargs: MultiseedExecutionOutcome(
            run_summaries=[build_summary(config_path, seed=42, run_id="run-001")],
            failures=[],
        ),
    )
    monkeypatch.setattr(
        "evo_system.experimentation.multiseed_run.create_multiseed_dir",
        lambda: tmp_path / "multiseed_20260330_120000",
    )

    def fake_run_post_multiseed_analysis(**kwargs):
        multiseed_dir = kwargs["multiseed_dir"]
        (multiseed_dir / CHAMPIONS_ANALYSIS_DIRNAME).mkdir(parents=True, exist_ok=True)
        (multiseed_dir / POST_MULTISEED_VALIDATION_DIRNAME / "external").mkdir(parents=True, exist_ok=True)
        (multiseed_dir / POST_MULTISEED_VALIDATION_DIRNAME / "audit").mkdir(parents=True, exist_ok=True)
        (multiseed_dir / MULTISEED_QUICK_SUMMARY_NAME).write_text("quick", encoding="utf-8")
        (multiseed_dir / MULTISEED_CHAMPIONS_SUMMARY_NAME).write_text("champions", encoding="utf-8")
        return type(
            "Result",
            (),
            {
                "summary_path": kwargs["summary_path"],
                "quick_summary_path": multiseed_dir / MULTISEED_QUICK_SUMMARY_NAME,
                "champions_summary_path": multiseed_dir / MULTISEED_CHAMPIONS_SUMMARY_NAME,
                "champions_analysis_dir": multiseed_dir / CHAMPIONS_ANALYSIS_DIRNAME,
                "external_output_dir": multiseed_dir / POST_MULTISEED_VALIDATION_DIRNAME / "external",
                "audit_output_dir": multiseed_dir / POST_MULTISEED_VALIDATION_DIRNAME / "audit",
            },
        )()

    monkeypatch.setattr(
        "evo_system.experimentation.multiseed_run.run_post_multiseed_analysis",
        fake_run_post_multiseed_analysis,
    )

    summary_path = run_multiseed_experiment(
        configs_dir=tmp_path,
        dataset_root=tmp_path / "datasets",
        parallel_workers=1,
    )

    multiseed_dir = tmp_path / "multiseed_20260330_120000"
    assert summary_path == multiseed_dir / MULTISEED_RUN_SUMMARY_NAME
    assert (multiseed_dir / MULTISEED_QUICK_SUMMARY_NAME).exists()
    assert (multiseed_dir / MULTISEED_CHAMPIONS_SUMMARY_NAME).exists()
    assert (multiseed_dir / CHAMPIONS_ANALYSIS_DIRNAME).exists()
    assert (multiseed_dir / POST_MULTISEED_VALIDATION_DIRNAME / "external").exists()
    assert (multiseed_dir / POST_MULTISEED_VALIDATION_DIRNAME / "audit").exists()


def test_run_multiseed_experiment_skip_post_analysis_keeps_real_summaries(
    monkeypatch,
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "run_a.json"
    write_config(config_path, extra_fields={"population_size": 18, "target_population_size": 18})

    monkeypatch.setattr(
        "evo_system.experimentation.multiseed_run.execute_multiseed_runs_with_failures",
        lambda **kwargs: MultiseedExecutionOutcome(
            run_summaries=[build_summary(config_path, seed=42, run_id="run-001")],
            failures=["run_a.json seed 103: boom"],
        ),
    )
    monkeypatch.setattr(
        "evo_system.experimentation.multiseed_run.create_multiseed_dir",
        lambda: tmp_path / "multiseed_20260330_130000",
    )

    with pytest.raises(RuntimeError, match="seed 103: boom"):
        run_multiseed_experiment(
            configs_dir=tmp_path,
            dataset_root=tmp_path / "datasets",
            parallel_workers=1,
            skip_post_multiseed_analysis=True,
        )

    multiseed_dir = tmp_path / "multiseed_20260330_130000"
    summary_text = (multiseed_dir / MULTISEED_RUN_SUMMARY_NAME).read_text(encoding="utf-8")
    quick_text = (multiseed_dir / MULTISEED_QUICK_SUMMARY_NAME).read_text(encoding="utf-8")
    assert "Ranking by champion rate and mean validation selection score" in summary_text
    assert "Seeds planned: 6" in quick_text
    assert "Seeds completed: 1" in quick_text
    assert "Seeds failed: 1" in quick_text
    assert not (multiseed_dir / CHAMPIONS_ANALYSIS_DIRNAME).exists()


def test_format_effective_dataset_roots_uses_single_resolved_value() -> None:
    assert format_effective_dataset_roots([DEFAULT_DATASET_ROOT]) == "data\\datasets"

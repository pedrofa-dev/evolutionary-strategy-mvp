import json
from pathlib import Path

from evo_system.experimentation.dataset_roots import (
    DEFAULT_DATASET_ROOT,
    DEFAULT_MANIFEST_DATASET_ROOT,
    format_effective_dataset_roots,
    resolve_dataset_root,
)
from evo_system.experimentation.presets import (
    apply_preset_to_seeds,
    get_available_preset_names,
    get_preset_by_name,
)
from evo_system.experimentation.batch_run import (
    BatchJob,
    calculate_effective_parallel_workers as calculate_batch_effective_parallel_workers,
    collect_active_job_lines as collect_batch_active_job_lines,
    execute_batch_jobs,
    format_parallel_progress as format_batch_parallel_progress,
    run_batch_experiment,
)
from evo_system.experimentation.cli import build_parser
from evo_system.experimentation.multiseed_run import (
    build_default_multiseed_seeds,
    build_multiseed_jobs,
    calculate_effective_parallel_workers as calculate_multiseed_effective_parallel_workers,
    execute_multiseed_runs,
    format_seed_plan,
    resolve_config_seeds,
    resolve_seed_map,
    run_multiseed_experiment,
)
from evo_system.experimentation.single_run import execute_historical_run
from evo_system.experimentation.parallel_progress import format_active_job_progress


def test_cli_parses_parallel_workers_for_batch_and_multiseed() -> None:
    parser = build_parser()

    batch_args = parser.parse_args(
        ["batch", "--configs-dir", "configs/runs", "--parallel-workers", "3"]
    )
    multiseed_args = parser.parse_args(
        ["multiseed", "--configs-dir", "configs/runs", "--parallel-workers", "4"]
    )

    assert batch_args.parallel_workers == 3
    assert multiseed_args.parallel_workers == 4


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
    assert extended.generations == 25
    assert extended.max_seeds == 10
    assert full.generations == 25
    assert full.max_seeds == 20

    seeds = [101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111]
    assert apply_preset_to_seeds(seeds, standard) == seeds[:6]
    assert apply_preset_to_seeds(seeds, extended) == seeds[:10]
    assert apply_preset_to_seeds(seeds, full) == seeds[:20]


def test_manifest_dataset_root_resolution_uses_data_datasets_by_default() -> None:
    assert resolve_dataset_root(DEFAULT_DATASET_ROOT, "manifest") == DEFAULT_MANIFEST_DATASET_ROOT
    assert resolve_dataset_root(DEFAULT_DATASET_ROOT, "legacy") == DEFAULT_DATASET_ROOT


def test_execute_historical_run_uses_manifest_dataset_root_by_default(
    monkeypatch,
    tmp_path: Path,
) -> None:
    captured_dataset_root: dict[str, Path] = {}

    class StopAfterDatasetLoad(Exception):
        pass

    def fake_load_paths(self, dataset_root: Path, dataset_mode: str, dataset_catalog_id: str | None):
        captured_dataset_root["value"] = dataset_root
        raise StopAfterDatasetLoad

    monkeypatch.setattr(
        "evo_system.experimentation.single_run.DatasetPoolLoader.load_paths",
        fake_load_paths,
    )

    config_path = tmp_path / "run_balanced_manifest.json"
    config_path.write_text(
        (
            "{"
            '"population_size": 18,'
            '"target_population_size": 18,'
            '"survivors_count": 4,'
            '"generations_planned": 40,'
            '"mutation_seed": 42,'
            '"dataset_mode": "manifest",'
            '"dataset_catalog_id": "core_1h_spot"'
            "}"
        ),
        encoding="utf-8",
    )

    try:
        execute_historical_run(config_path=config_path)
    except StopAfterDatasetLoad:
        pass

    assert captured_dataset_root["value"] == DEFAULT_MANIFEST_DATASET_ROOT


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
    assert calculate_batch_effective_parallel_workers(1, 2) == 1
    assert calculate_multiseed_effective_parallel_workers(1, 4) == 1
    assert calculate_batch_effective_parallel_workers(3, 8) == 3


def test_format_parallel_progress_is_human_readable() -> None:
    progress_line = format_batch_parallel_progress(
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


def test_execute_batch_jobs_keeps_sequential_behavior_when_workers_equal_one(
    monkeypatch,
    tmp_path: Path,
) -> None:
    calls: list[str] = []

    class Summary:
        def __init__(self, name: str) -> None:
            self.config_name = name
            self.run_id = f"run-{name}"
            self.mutation_seed = 42
            self.best_train_selection_score = 1.0
            self.final_validation_selection_score = 1.0
            self.final_validation_profit = 1.0
            self.final_validation_drawdown = 0.1
            self.final_validation_trades = 10.0
            self.train_validation_selection_gap = 0.0
            self.train_validation_profit_gap = 0.0
            self.best_genome_repr = "genome"
            self.log_file_path = tmp_path / f"{name}.txt"

    def fake_execute_historical_run(
        config_path: Path,
        output_dir: Path,
        log_name: str,
        dataset_root: Path,
    ):
        calls.append(config_path.name)
        return Summary(config_path.stem)

    monkeypatch.setattr(
        "evo_system.experimentation.batch_run.execute_historical_run",
        fake_execute_historical_run,
    )

    config_files = [tmp_path / "a.json", tmp_path / "b.json"]
    for path in config_files:
        path.write_text("{}", encoding="utf-8")

    summaries = execute_batch_jobs(
        config_files=config_files,
        batch_dir=tmp_path / "batch",
        dataset_root=tmp_path / "datasets",
        requested_parallel_workers=1,
    )

    assert calls == ["a.json", "b.json"]
    assert len(summaries) == 2


def test_execute_batch_jobs_parallel_path_uses_process_executor(
    monkeypatch,
    tmp_path: Path,
) -> None:
    submitted_jobs: list[BatchJob] = []

    class FakeFuture:
        def __init__(self, value):
            self._value = value

        def result(self):
            return self._value

    class Summary:
        def __init__(self, name: str) -> None:
            self.config_name = name
            self.run_id = f"run-{name}"
            self.mutation_seed = 42
            self.best_train_selection_score = 1.0
            self.final_validation_selection_score = 1.0
            self.final_validation_profit = 1.0
            self.final_validation_drawdown = 0.1
            self.final_validation_trades = 10.0
            self.train_validation_selection_gap = 0.0
            self.train_validation_profit_gap = 0.0
            self.best_genome_repr = "genome"
            self.log_file_path = tmp_path / f"{name}.txt"

    class FakeExecutor:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def submit(self, fn, job):
            submitted_jobs.append(job)
            return FakeFuture(Summary(job.config_path.stem))

    def fake_wait(futures, timeout, return_when):
        return set(futures), set()

    monkeypatch.setattr(
        "evo_system.experimentation.batch_run.ProcessPoolExecutor",
        FakeExecutor,
    )
    monkeypatch.setattr(
        "evo_system.experimentation.batch_run.wait",
        fake_wait,
    )

    config_files = [tmp_path / "a.json", tmp_path / "b.json"]
    for path in config_files:
        path.write_text("{}", encoding="utf-8")

    summaries = execute_batch_jobs(
        config_files=config_files,
        batch_dir=tmp_path / "batch",
        dataset_root=tmp_path / "datasets",
        requested_parallel_workers=2,
    )

    assert [job.config_path.name for job in submitted_jobs] == ["a.json", "b.json"]
    assert len(summaries) == 2


def test_execute_batch_jobs_prints_fallback_message_when_parallel_is_not_useful(
    monkeypatch,
    capsys,
    tmp_path: Path,
) -> None:
    class Summary:
        def __init__(self) -> None:
            self.config_name = "a"
            self.run_id = "run-a"
            self.mutation_seed = 42
            self.best_train_selection_score = 1.0
            self.final_validation_selection_score = 1.0
            self.final_validation_profit = 1.0
            self.final_validation_drawdown = 0.1
            self.final_validation_trades = 10.0
            self.train_validation_selection_gap = 0.0
            self.train_validation_profit_gap = 0.0
            self.best_genome_repr = "genome"
            self.log_file_path = tmp_path / "a.txt"

    monkeypatch.setattr(
        "evo_system.experimentation.batch_run.execute_historical_run",
        lambda config_path, output_dir, log_name, dataset_root: Summary(),
    )

    config_file = tmp_path / "a.json"
    config_file.write_text("{}", encoding="utf-8")

    execute_batch_jobs(
        config_files=[config_file],
        batch_dir=tmp_path / "batch",
        dataset_root=tmp_path / "datasets",
        requested_parallel_workers=2,
    )

    captured = capsys.readouterr()
    assert "Falling back to sequential execution." in captured.out


def test_collect_active_job_lines_reads_snapshot_files(tmp_path: Path) -> None:
    snapshot_path = tmp_path / "progress_a.json"
    snapshot_path.write_text(
        json.dumps(
            {
                "config_name": "run_balanced_manifest",
                "mutation_seed": None,
                "current_generation": 18,
                "total_generations": 40,
                "validation_selection": 1.92,
                "elapsed_seconds": 614,
            }
        ),
        encoding="utf-8",
    )

    job = BatchJob(
        config_path=tmp_path / "run_balanced_manifest.json",
        output_dir=tmp_path,
        dataset_root=tmp_path,
        log_name="run.txt",
        progress_snapshot_path=snapshot_path,
    )

    lines = collect_batch_active_job_lines([job])

    assert lines == [
        "- run_balanced_manifest | gen 18/40 | validation_selection=1.9200 | elapsed=10:14"
    ]


def test_execute_multiseed_runs_keeps_sequential_run_output_path(
    monkeypatch,
    tmp_path: Path,
) -> None:
    calls: list[str] = []

    class Summary:
        def __init__(self, name: str, seed: int) -> None:
            self.config_name = name
            self.run_id = f"run-{name}-{seed}"
            self.mutation_seed = seed
            self.best_train_selection_score = 1.0
            self.final_validation_selection_score = 1.0
            self.final_validation_profit = 1.0
            self.final_validation_drawdown = 0.1
            self.final_validation_trades = 10.0
            self.train_validation_selection_gap = 0.0
            self.train_validation_profit_gap = 0.0
            self.best_genome_repr = "genome"
            self.log_file_path = tmp_path / f"{name}_{seed}.txt"

    def fake_execute_historical_run(
        config_path: Path,
        output_dir: Path,
        log_name: str,
        config_name_override: str,
        dataset_root: Path,
        context_name,
        progress_snapshot_path: Path,
    ):
        calls.append(config_name_override)
        return Summary(config_name_override, 101)

    monkeypatch.setattr(
        "evo_system.experimentation.multiseed_run.execute_historical_run",
        fake_execute_historical_run,
    )

    config_path = tmp_path / "a.json"
    config_path.write_text(
        (
            "{"
            '"mutation_seed": 42,'
            '"population_size": 12,'
            '"target_population_size": 12,'
            '"survivors_count": 4,'
            '"generations_planned": 25'
            "}"
        ),
        encoding="utf-8",
    )

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


def test_resolve_config_seeds_uses_explicit_seeds_when_present(tmp_path: Path) -> None:
    config_path = tmp_path / "a.json"
    config_path.write_text(
        (
            "{"
            '"mutation_seed": 42,'
            '"population_size": 12,'
            '"target_population_size": 12,'
            '"survivors_count": 4,'
            '"generations_planned": 25,'
            '"seeds": [201, 202, 203]'
            "}"
        ),
        encoding="utf-8",
    )

    assert resolve_config_seeds(config_path) == [201, 202, 203]


def test_resolve_config_seeds_uses_seed_range_when_present(tmp_path: Path) -> None:
    config_path = tmp_path / "a.json"
    config_path.write_text(
        (
            "{"
            '"mutation_seed": 42,'
            '"population_size": 12,'
            '"target_population_size": 12,'
            '"survivors_count": 4,'
            '"generations_planned": 25,'
            '"seed_start": 100,'
            '"seed_count": 4'
            "}"
        ),
        encoding="utf-8",
    )

    assert resolve_config_seeds(config_path) == [100, 101, 102, 103]


def test_resolve_config_seeds_falls_back_to_default_seed_plan(tmp_path: Path) -> None:
    config_path = tmp_path / "a.json"
    config_path.write_text(
        (
            "{"
            '"mutation_seed": 42,'
            '"population_size": 12,'
            '"target_population_size": 12,'
            '"survivors_count": 4,'
            '"generations_planned": 25'
            "}"
        ),
        encoding="utf-8",
    )

    assert resolve_config_seeds(config_path) == build_default_multiseed_seeds()


def test_resolve_seed_map_applies_presets_to_config_defined_seeds(tmp_path: Path) -> None:
    config_path = tmp_path / "a.json"
    config_path.write_text(
        (
            "{"
            '"mutation_seed": 42,'
            '"population_size": 12,'
            '"target_population_size": 12,'
            '"survivors_count": 4,'
            '"generations_planned": 25,'
            '"seeds": [201, 202, 203, 204, 205, 206, 207]'
            "}"
        ),
        encoding="utf-8",
    )

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
    config_path.write_text(
        (
            "{"
            '"population_size": 18,'
            '"target_population_size": 18,'
            '"survivors_count": 4,'
            '"generations_planned": 40,'
            '"mutation_seed": 42,'
            '"dataset_mode": "manifest",'
            '"dataset_catalog_id": "core_1h_spot"'
            "}"
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "evo_system.experimentation.multiseed_run.execute_multiseed_runs",
        lambda **kwargs: [],
    )
    monkeypatch.setattr(
        "evo_system.experimentation.multiseed_run.create_multiseed_dir",
        lambda: tmp_path / "out",
    )
    monkeypatch.setattr(
        "evo_system.experimentation.multiseed_run.write_multiseed_summary",
        lambda **kwargs: tmp_path / "summary.txt",
    )

    run_multiseed_experiment(
        configs_dir=tmp_path,
        dataset_root=DEFAULT_DATASET_ROOT,
        preset_name="screening",
        parallel_workers=1,
    )

    captured = capsys.readouterr()
    assert "Dataset root: data\\datasets" in captured.out


def test_run_batch_experiment_reports_effective_manifest_dataset_root(
    monkeypatch,
    capsys,
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "run_balanced_manifest.json"
    config_path.write_text(
        (
            "{"
            '"population_size": 18,'
            '"target_population_size": 18,'
            '"survivors_count": 4,'
            '"generations_planned": 40,'
            '"mutation_seed": 42,'
            '"dataset_mode": "manifest",'
            '"dataset_catalog_id": "core_1h_spot"'
            "}"
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "evo_system.experimentation.batch_run.execute_batch_jobs",
        lambda **kwargs: [],
    )
    monkeypatch.setattr(
        "evo_system.experimentation.batch_run.create_batch_dir",
        lambda: tmp_path / "out",
    )
    monkeypatch.setattr(
        "evo_system.experimentation.batch_run.write_batch_summary",
        lambda **kwargs: tmp_path / "summary.txt",
    )

    run_batch_experiment(
        configs_dir=tmp_path,
        dataset_root=DEFAULT_DATASET_ROOT,
        parallel_workers=1,
    )

    captured = capsys.readouterr()
    assert "Dataset root: data\\datasets" in captured.out


def test_format_effective_dataset_roots_uses_single_resolved_value() -> None:
    assert format_effective_dataset_roots([DEFAULT_MANIFEST_DATASET_ROOT]) == "data\\datasets"

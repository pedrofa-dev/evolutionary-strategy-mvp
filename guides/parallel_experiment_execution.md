# Parallel Experiment Execution

The multiseed experiment mode supports optional process-based parallel execution.

## Why Processes

Independent experiment runs are isolated units of work, so process-based parallelism is preferred over threads for CPU-bound workloads and Windows-friendly isolation.

## Supported Modes

Parallel execution is supported for:

- `multiseed`

## Usage

Use `--parallel-workers N` to enable multiple worker processes.

Examples:

```bash
python scripts/run_experiment.py --configs-dir configs/runs --preset screening --parallel-workers 4
```

If `--parallel-workers 1` is used, behavior stays sequential.

If parallel execution is requested but only one job is effectively scheduled, the system prints an explicit fallback message and continues sequentially.

## What Remains Sequential

- the evolution loop inside a single run
- evaluation inside a single run
- champion selection inside a single run

Only independent run jobs are parallelized.

## Caveats

- Windows uses spawn semantics, so worker functions must stay at top level.
- Requested workers and effective workers may differ if too few jobs are scheduled.
- Run logs and artifact files remain separate per job.
- In parallel mode, failures are collected and summarized at the end instead of failing on the first error.

## Progress Display

Sequential mode keeps the normal detailed run output, including generation-level visibility from each run.

Parallel mode keeps workers quiet to avoid interleaved logs, and the parent process prints overall progress lines such as:

```text
[3/10] completed | success=3 | failed=0 | last=run_balanced seed=103
```

For longer runs, workers also write small progress snapshots and the parent prints the latest known active-job status on a throttled cadence. Example:

```text
Completed: 1/5 | success=1 | failed=0
Active jobs:
- run_balanced_manifest seed=102 | gen 18/40 | validation_selection=1.9200 | elapsed=10:14
- run_balanced_manifest seed=103 | gen 17/40 | validation_selection=0.8400 | elapsed=09:51
```

Sequential mode keeps the existing detailed generation-by-generation console output.

Parallel active-job updates are refreshed at most once every five seconds, plus completion and failure events. Snapshot files are unique per job and are cleaned up by the parent process after each job finishes.

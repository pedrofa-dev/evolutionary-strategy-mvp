🚀 Usage Guide

This section explains how to use the full pipeline step by step.

🔁 Full Pipeline
download_data → build_datasets → run_experiment → analyze_champions

You can execute each step independently.

📥 1. Download Market Data

Unified entrypoint for both spot and futures:

Spot
python scripts/download_data.py spot \
  --symbols BTCUSDT ETHUSDT \
  --interval 1h \
  --start 2020-01-01 \
  --end 2023-01-01
Futures
python scripts/download_data.py futures \
  --symbols BTCUSDT ETHUSDT \
  --interval 1h \
  --start 2020-01-01 \
  --end 2023-01-01
Common options
--symbols → list of markets
--interval → timeframe (e.g. 1m, 5m, 1h, 1d)
--start / --end → date range
🧱 2. Build Datasets

Convert raw data into training/validation datasets.

python scripts/build_datasets.py \
  --input-dir data/raw \
  --output-dir data/processed
What this does
normalizes data
splits datasets
prepares them for backtesting
🧪 3. Run Experiments

Main entrypoint:

python scripts/run_experiment.py <mode> [options]
🔹 Single Run

Run a single configuration:

python scripts/run_experiment.py single \
  --config configs/runs/run_balanced.json \
  --dataset-root data/processed
🔹 Batch Run

Run multiple configs:

python scripts/run_experiment.py batch \
  --configs-dir configs/runs \
  --dataset-root data/processed
🔹 Multiseed Run

Run multiple configs across multiple seeds:

python scripts/run_experiment.py multiseed \
  --configs-dir configs/runs \
  --dataset-root data/processed \
  --preset screening
🧩 Presets

Presets define how many seeds and generations are used.

screening
faster
exploratory
useful for comparing configs
full
slower
more stable
better for validation
🧠 Important Behavior
Only one champion per run is persisted
It is the best persistable champion across the run
Not necessarily from the final generation
📊 4. Analyze Champions
python scripts/analyze_champions.py
What it does
loads champions from SQLite
groups by config
computes statistics
outputs summary reports
Optional filters (if implemented)
--config run_balanced
--champion-type robust
--limit 10
🧪 Example Full Workflow
# 1. Download data
python scripts/download_data.py spot --symbols BTCUSDT --interval 1h

# 2. Build datasets
python scripts/build_datasets.py

# 3. Run experiments
python scripts/run_experiment.py multiseed \
  --configs-dir configs/runs \
  --dataset-root data/processed \
  --preset screening

# 4. Analyze results
python scripts/analyze_champions.py
⚙️ Config Files

Configs are JSON files defining evolution parameters.

Example:

{
  "population_size": 18,
  "target_population_size": 18,
  "survivors_count": 4,
  "generations_planned": 25,
  "mutation_seed": 42,
  "trade_cost_rate": 0.0,
  "cost_penalty_weight": 0.0,
  "mutation_profile": {
    "strong_mutation_probability": 0.055,
    "numeric_delta_scale": 0.75,
    "flag_flip_probability": 0.025,
    "weight_delta": 0.145,
    "window_step_mode": "default"
  }
}
🧠 Tips
1. Start with screening

Use screening preset to:

compare configs
iterate fast
2. Use multiseed for validation

Single runs are noisy.

Multiseed reveals:

stability
robustness
3. Keep configs small first

Before scaling:

test logic
validate pipeline
4. Analyze before optimizing

Don’t just run experiments:
👉 inspect champions and patterns

🏁 Summary

You now have a clean and consistent workflow:

data → datasets → experiments → champions → insights
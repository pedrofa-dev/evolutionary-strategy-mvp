🧠 System Architecture Overview

This project is structured as a modular evolutionary trading system.
Each part of the system has a clearly defined responsibility, allowing independent evolution of:

data ingestion
evaluation logic
experiment execution
champion selection
reporting
🔁 End-to-End Pipeline
download_data
→ build_datasets
→ run_experiment
→ analyze_champions
📁 Project Structure
src/evo_system/

  ingestion/        # Market data acquisition
  environment/      # Historical simulation environments
  domain/           # Core data models (Agent, Genome, Evaluation, etc.)
  evaluation/       # Agent evaluation (scoring, penalties, vetoes)
  champions/        # Champion policy and selection logic
  experimentation/  # Experiment orchestration (single, batch, multiseed)
  storage/          # Persistence layer (SQLite)
  reporting/        # Analysis and reporting of results

scripts/

  download_data.py      # Data ingestion CLI
  build_datasets.py     # Dataset preparation
  run_experiment.py     # Main experiment entrypoint
  analyze_champions.py  # Reporting CLI
🧩 Module Responsibilities
🟢 ingestion/

Handles downloading raw market data (spot and futures).

Provides a unified CLI (download_data.py)
Abstracts differences between market types
Produces raw data used to build datasets

👉 “How do we get market data?”

🌍 environment/

Simulates trading environments using historical data.

Runs agent episodes on datasets
Produces profit, drawdown, trades, cost, etc.

👉 “How do we simulate the market?”

🧱 domain/

Defines core entities of the system.

Examples:

Agent
Genome
AgentEvaluation
HistoricalRunSummary

👉 “What are the core objects of the system?”

📊 evaluation/

Evaluates agent performance across datasets.

Submodules:
scoring.py → score construction logic
penalties.py → soft penalties (e.g. dispersion)
vetoes.py → hard constraints (e.g. too few trades)
evaluator.py → orchestrates evaluation

Key rules:

Hard vetoes:
too_few_trades
position_size_too_small
take_profit_too_small
Soft penalty:
dispersion_too_high

👉 “How good is this agent?”

🏆 champions/

Defines what qualifies as a champion.

Responsibilities:
Classification:
robust
specialist
rejected
Champion rules and thresholds
Champion comparison (best-of-run selection)
Champion metrics construction
Persistence eligibility

👉 “What is a valid trading strategy?”

🧪 experimentation/

Controls experiment execution.

Features:
Single runs
Batch runs (multiple configs)
Multiseed runs (stability testing)
Presets (screening, full, etc.)
Key behavior:
Tracks best persistable champion during the run
Persists only one champion per run
Does not depend on final generation

👉 “How do we run experiments?”

💾 storage/

Handles persistence using SQLite.

Responsibilities:
Save runs
Save champions
Load stored results

👉 “Where do we store results?”

📈 reporting/

Analyzes stored results.

Submodules:
champion_loader.py → load from DB
champion_queries.py → filtering and grouping
champion_stats.py → statistics
champion_card.py → individual summaries
report_builder.py → full report assembly
Important:
Uses champion_type stored in DB as source of truth
Does NOT reimplement champion logic

👉 “What can we learn from past results?”

🧰 Scripts (Entry Points)

Scripts are thin wrappers around the system:

python scripts/download_data.py ...
python scripts/build_datasets.py ...
python scripts/run_experiment.py ...
python scripts/analyze_champions.py ...

They:

parse arguments
call internal modules
contain no business logic
🧠 Design Principles
1. Clear separation of concerns

Each module has a single responsibility:

evaluation ≠ champions ≠ reporting
2. No duplicated logic
Champion logic exists only in champions/
Evaluation logic exists only in evaluation/
Reporting never redefines system behavior
3. Execution vs Analysis
Execution flow:
ingestion → environment → evaluation → champions → storage
Analysis flow:
storage → reporting
4. Single entrypoints
One script per operation
No duplicated scripts
No legacy wrappers
5. Extensibility

You can independently evolve:

scoring models
champion rules
experiment strategies
reporting logic

without breaking other layers.

🏁 Summary

The system is organized into two main domains:

Execution
ingestion
environment
evaluation
champions
experimentation
storage
Analysis
reporting

This architecture ensures:

maintainability
clarity
scalability
and safe iteration over trading strategies
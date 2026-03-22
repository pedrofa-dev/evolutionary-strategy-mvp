from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class HistoricalRunSummary:
    config_name: str
    run_id: str
    log_file_path: Path
    best_train_selection_score: float
    final_validation_selection_score: float
    final_validation_profit: float
    final_validation_drawdown: float
    final_validation_trades: float
    best_genome_repr: str
    generation_of_best: int
    train_validation_selection_gap: float
    train_validation_profit_gap: float
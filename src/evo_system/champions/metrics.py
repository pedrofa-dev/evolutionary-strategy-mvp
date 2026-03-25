from pathlib import Path

from evo_system.champions.classifier import (
    classify_champion,
    count_positive_and_negative_datasets,
)
from evo_system.domain.agent_evaluation import AgentEvaluation


def format_dataset_path(path: Path, dataset_root: Path) -> str:
    try:
        return str(path.relative_to(dataset_root))
    except ValueError:
        return str(path)


def build_dataset_signature(
    all_train_dataset_paths: list[Path],
    validation_dataset_paths: list[Path],
    dataset_root: Path,
    train_sample_size: int,
) -> str:
    import json
    from hashlib import sha256

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
    positive_datasets, negative_datasets = count_positive_and_negative_datasets(
        validation_evaluation.dataset_profits
    )
    champion_type = classify_champion(
        train_evaluation=train_evaluation,
        validation_evaluation=validation_evaluation,
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
        "champion_type": champion_type,
        "champion_status": "candidate",
        "positive_validation_datasets": positive_datasets,
        "negative_validation_datasets": negative_datasets,
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

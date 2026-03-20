from pathlib import Path

from run_historical import execute_historical_run


CONFIGS_DIR = Path("configs/runs")


def main() -> None:
    config_files = sorted(CONFIGS_DIR.glob("*.json"))

    if not config_files:
        print("No config files found.")
        return

    print(f"Found {len(config_files)} config files.")

    generated_logs: list[Path] = []

    for config_path in config_files:
        print()
        print(f"=== Running {config_path.name} ===")
        log_file_path = execute_historical_run(config_path)
        generated_logs.append(log_file_path)

    print()
    print("Batch completed.")
    print("Generated logs:")
    for log_file_path in generated_logs:
        print(f" - {log_file_path}")


if __name__ == "__main__":
    main()
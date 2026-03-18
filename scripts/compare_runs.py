import sqlite3
from pathlib import Path


DATABASE_PATH = Path("data/evolution.db")


def main() -> None:
    if not DATABASE_PATH.exists():
        print("Database not found.")
        return

    with sqlite3.connect(DATABASE_PATH) as connection:
        cursor = connection.execute(
            """
            SELECT
                r.run_id,
                r.mutation_seed,
                r.population_size,
                r.target_population_size,
                r.survivors_count,
                r.generations_planned,
                gr.generation_number,
                gr.best_fitness,
                gr.average_fitness
            FROM runs r
            JOIN generation_results gr
                ON r.run_id = gr.run_id
            WHERE gr.generation_number = (
                SELECT MAX(gr2.generation_number)
                FROM generation_results gr2
                WHERE gr2.run_id = r.run_id
            )
            ORDER BY gr.best_fitness DESC, gr.average_fitness DESC
            """
        )

        rows = cursor.fetchall()

    if not rows:
        print("No run results found.")
        return

    print("\nRun comparison by final generation:\n")

    for row in rows:
        (
            run_id,
            mutation_seed,
            population_size,
            target_population_size,
            survivors_count,
            generations_planned,
            generation_number,
            best_fitness,
            average_fitness,
        ) = row

        print(
            f"Run ID: {run_id} | "
            f"Seed: {mutation_seed} | "
            f"Population: {population_size} -> {target_population_size} | "
            f"Survivors: {survivors_count} | "
            f"Final generation: {generation_number} | "
            f"Best fitness: {best_fitness:.4f} | "
            f"Average fitness: {average_fitness:.4f}"
        )


if __name__ == "__main__":
    main()
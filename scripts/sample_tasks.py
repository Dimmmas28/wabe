#!/usr/bin/env python
"""
Sample random tasks from scenario_full.toml by difficulty level.

Usage:
    python scripts/sample_tasks.py
    python scripts/sample_tasks.py --count 5  # 5 of each level
    python scripts/sample_tasks.py --seed 42  # reproducible sampling
"""

import argparse
import random
from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib


def load_tasks(toml_path: Path) -> list[dict]:
    """Load tasks from a TOML scenario file."""
    with open(toml_path, "rb") as f:
        data = tomllib.load(f)
    return data.get("tasks", [])


def sample_by_level(
    tasks: list[dict], count: int = 3, seed: int | None = None
) -> dict[str, list[dict]]:
    """Sample tasks by difficulty level."""
    if seed is not None:
        random.seed(seed)

    # Group by level
    by_level: dict[str, list[dict]] = {"easy": [], "medium": [], "hard": []}
    for task in tasks:
        level = task.get("level", "medium")
        if level in by_level:
            by_level[level].append(task)

    # Sample from each level
    sampled = {}
    for level, level_tasks in by_level.items():
        n = min(count, len(level_tasks))
        sampled[level] = random.sample(level_tasks, n)

    return sampled


def format_task(task: dict) -> str:
    """Format a task for display."""
    return f'  task_id = "{task["task_id"]}"\n  task = "{task["task"]}"\n  website = "{task["website"]}"'


def format_as_toml(tasks: list[dict]) -> str:
    """Format tasks as TOML [[tasks]] entries."""
    lines = []
    for task in tasks:
        lines.append("[[tasks]]")
        lines.append(f'task_id = "{task["task_id"]}"')
        # Handle multi-line task descriptions
        task_desc = task["task"].replace('"', '\\"')
        if "\n" in task_desc:
            lines.append(f'task = """{task_desc}"""')
        else:
            lines.append(f'task = "{task_desc}"')
        lines.append(f'website = "{task["website"]}"')
        lines.append(f'reference_length = {task.get("reference_length", 5)}')
        lines.append(f'level = "{task.get("level", "medium")}"')
        lines.append("")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Sample tasks by difficulty level")
    parser.add_argument(
        "--count", "-n", type=int, default=3, help="Number of tasks per level"
    )
    parser.add_argument(
        "--seed", "-s", type=int, help="Random seed for reproducibility"
    )

    args = parser.parse_args()

    # Find the scenario file
    script_dir = Path(__file__).parent
    toml_path = script_dir.parent / "scenarios/web_browser/scenario_full.toml"

    if not toml_path.exists():
        print(f"Error: {toml_path} not found")
        return 1

    tasks = load_tasks(toml_path)
    print(f"Loaded {len(tasks)} tasks from {toml_path.name}\n")

    sampled = sample_by_level(tasks, count=args.count, seed=args.seed)

    # Always output as TOML format for easy copying
    all_sampled = []
    for level in ["easy", "medium", "hard"]:
        all_sampled.extend(sampled[level])
    print(format_as_toml(all_sampled))

    return 0


if __name__ == "__main__":
    exit(main())

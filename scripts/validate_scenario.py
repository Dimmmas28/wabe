#!/usr/bin/env python
"""
Validate scenario TOML files for task uniqueness and required fields.

Usage:
    python scripts/validate_scenario.py scenarios/web_browser/scenario.toml
    python scripts/validate_scenario.py scenarios/web_browser/*.toml
    python scripts/validate_scenario.py -v scenarios/web_browser/scenario.toml
"""

import argparse
import sys
from pathlib import Path
from typing import NamedTuple

try:
    import tomllib
except ImportError:
    import tomli as tomllib


VALID_LEVELS = {"easy", "medium", "hard"}
REQUIRED_FIELDS = ["task_id", "task", "website"]


class ValidationResult(NamedTuple):
    errors: list[str]
    warnings: list[str]
    stats: dict[str, dict[str, float | int]]


def validate_scenario(path: Path) -> ValidationResult:
    """Validate a single scenario file."""
    errors: list[str] = []
    warnings: list[str] = []

    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
    except Exception as e:
        return ValidationResult(
            errors=[f"Failed to parse TOML: {e}"], warnings=[], stats={}
        )

    tasks = data.get("tasks", [])
    if not tasks:
        return ValidationResult(
            errors=[], warnings=["No tasks found in file"], stats={}
        )

    # Track duplicates
    seen_task_ids: dict[str, int] = {}
    seen_task_texts: dict[str, int] = {}

    # Stats tracking
    level_counts: dict[str, int] = {"easy": 0, "medium": 0, "hard": 0}
    level_ref_lengths: dict[str, list[int]] = {"easy": [], "medium": [], "hard": []}

    for idx, task in enumerate(tasks, start=1):
        task_id = task.get("task_id")
        task_text = task.get("task")
        website = task.get("website")
        level = task.get("level", "medium")
        ref_length = task.get("reference_length")

        # Check required fields
        for field in REQUIRED_FIELDS:
            if not task.get(field):
                errors.append(f"Task #{idx}: missing required field '{field}'")

        # Check for duplicate task_id
        if task_id:
            if task_id in seen_task_ids:
                errors.append(
                    f"Task #{idx}: duplicate task_id '{task_id}' "
                    f"(first seen at task #{seen_task_ids[task_id]})"
                )
            else:
                seen_task_ids[task_id] = idx

        # Check for duplicate task text (warning only)
        if task_text:
            normalized = task_text.strip()
            if normalized in seen_task_texts:
                warnings.append(
                    f"Task #{idx}: duplicate task description "
                    f"(first seen at task #{seen_task_texts[normalized]})"
                )
            else:
                seen_task_texts[normalized] = idx

        # Validate level
        if level and level not in VALID_LEVELS:
            warnings.append(
                f"Task #{idx}: invalid level '{level}' "
                f"(expected one of: {', '.join(sorted(VALID_LEVELS))})"
            )

        # Collect stats
        if level in level_counts:
            level_counts[level] += 1
            if ref_length is not None:
                level_ref_lengths[level].append(ref_length)

    # Compute statistics
    stats: dict[str, dict[str, float | int]] = {}
    for level in VALID_LEVELS:
        count = level_counts[level]
        ref_lengths = level_ref_lengths[level]
        mean_ref = sum(ref_lengths) / len(ref_lengths) if ref_lengths else 0.0
        stats[level] = {
            "count": count,
            "mean_reference_length": round(mean_ref, 2),
        }

    return ValidationResult(errors=errors, warnings=warnings, stats=stats)


def print_stats(stats: dict[str, dict[str, float | int]]) -> None:
    """Print statistics table."""
    print("\n  Statistics:")
    print("  " + "-" * 42)
    print(f"  {'Level':<10} {'Count':>8} {'Mean Ref Length':>18}")
    print("  " + "-" * 42)
    total_count = 0
    for level in ["easy", "medium", "hard"]:
        level_stats = stats.get(level, {"count": 0, "mean_reference_length": 0.0})
        count = level_stats["count"]
        mean_ref = level_stats["mean_reference_length"]
        total_count += count
        print(f"  {level:<10} {count:>8} {mean_ref:>18.2f}")
    print("  " + "-" * 42)
    print(f"  {'Total':<10} {total_count:>8}")


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Validate scenario TOML files for task uniqueness and required fields"
    )
    parser.add_argument(
        "files",
        nargs="+",
        type=Path,
        help="Scenario TOML file(s) to validate",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show warnings and statistics even when validation passes",
    )

    args = parser.parse_args()

    any_errors = False

    for filepath in args.files:
        if not filepath.exists():
            print(f"Error: File not found: {filepath}")
            any_errors = True
            continue

        result = validate_scenario(filepath)

        has_issues = result.errors or result.warnings
        if has_issues or args.verbose:
            print(f"\n{filepath}:")

        if result.errors:
            any_errors = True
            print("  Errors:")
            for error in result.errors:
                print(f"    - {error}")

        if result.warnings and (args.verbose or result.errors):
            print("  Warnings:")
            for warning in result.warnings:
                print(f"    - {warning}")

        if args.verbose and result.stats:
            print_stats(result.stats)

        if not has_issues and args.verbose:
            print("  All validations passed.")

    # Summary
    if len(args.files) > 1:
        status = "FAILED" if any_errors else "PASSED"
        print(f"\nValidation {status} for {len(args.files)} file(s)")

    return 1 if any_errors else 0


if __name__ == "__main__":
    sys.exit(main())

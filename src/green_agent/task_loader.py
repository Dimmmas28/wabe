import json
from pathlib import Path
from typing import List

from green_agent.models import Task


class TaskLoader:
    def __init__(self, tasks_dir: str):
        self.tasks_dir = Path(tasks_dir)

    def load_all_tasks(self) -> List[Task]:
        """Load all tasks from JSON files"""
        tasks = []

        # Load from tasks.json if exists
        tasks_file = self.tasks_dir / "tasks.json"
        if tasks_file.exists():
            with open(tasks_file) as f:
                data = json.load(f)
                for task_data in data:
                    tasks.append(Task(**task_data))

        # Load individual task files
        for task_file in self.tasks_dir.glob("task_*.json"):
            with open(task_file) as f:
                task_data = json.load(f)
                tasks.append(Task(**task_data))

        return tasks

    def load_task(self, task_id: str) -> Task:
        """Load a specific task"""
        task_file = self.tasks_dir / f"{task_id}.json"
        with open(task_file) as f:
            return Task(**json.load(f))

from typing import Any

from pydantic import BaseModel, HttpUrl


class EvalRequest(BaseModel):
    participants: dict[str, HttpUrl]  # role-endpoint mapping
    config: dict[str, Any]  # shared config (max_steps, etc.)
    tasks: list[dict[str, Any]] = []  # list of task configs for parallel execution


class EvalResult(BaseModel):
    winner: str  # role of winner
    detail: dict[str, Any]

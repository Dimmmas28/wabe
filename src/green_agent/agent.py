from abc import ABC, abstractmethod
from a2a.server.tasks import TaskUpdater
from pydantic import BaseModel, HttpUrl


class EvalRequest(BaseModel):
    white_agent_url: HttpUrl


class GreenAgent(ABC):
    @abstractmethod
    async def run_eval(self, request: EvalRequest, updater: TaskUpdater) -> None:
        pass

    @abstractmethod
    def validate_request(self, request: EvalRequest) -> tuple[bool, str]:
        pass

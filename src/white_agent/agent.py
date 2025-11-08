from abc import ABC, abstractmethod


class WhiteAgent(ABC):
    @abstractmethod
    async def invoke(self, task: str) -> str:
        """Run the agent against the provided task and return the response."""

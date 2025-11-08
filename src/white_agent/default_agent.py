from white_agent.agent import WhiteAgent


class DefaultWhiteAgent(WhiteAgent):
    async def invoke(self, task: str) -> str:
        return f"The assigned agent is unable to complete the specified task: {task}"

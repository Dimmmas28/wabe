import os

from langchain_google_genai import ChatGoogleGenerativeAI
from white_agent.agent import WhiteAgent
from langchain.messages import HumanMessage, SystemMessage


class DefaultWhiteAgent(WhiteAgent):
    def __init__(
        self,
        model_name: str = "gemini-2.5-pro",
        temperature: float = 1.0,
    ):
        """
        Initialize Gemini white agent

        Args:
            model_name: Gemini model to use (gemini-1.5-flash or gemini-1.5-pro)
            temperature: Temperature for generation (0.0 = deterministic)
            api_key: Google API key (if not in environment)
        """
        self.api_key = os.getenv("GOOGLE_API_KEY")

        if not self.api_key:
            raise ValueError(
                "Google API key not found. Set GOOGLE_API_KEY environment variable "
                "or pass api_key parameter"
            )

        self.llm = ChatGoogleGenerativeAI(
            model=model_name, temperature=temperature, google_api_key=self.api_key
        )

        self.system_prompt = """You are a helpful web automation agent. 
Your task is to help complete web navigation and interaction tasks.

When given a task, you should:
1. Think about what actions are needed
2. Respond with your reasoning and the specific action to take
3. Use the tools provided to interact with the web page

Always respond in the following format:
<json>
{
    "thought": "your reasoning about what to do",
    "tool": "tool_name",
    "params": {"param": "value"}
}
</json>
"""

    async def invoke(self, task: str) -> str:
        """
        Run the agent with the given task

        Args:
            task: Task description with context

        Returns:
            Agent's response as string
        """
        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=task),
        ]

        response = await self.llm.ainvoke(messages)
        return response.content

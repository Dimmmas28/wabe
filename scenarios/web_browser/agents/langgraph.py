"""
ReAct Pattern Web Agent using LangGraph

This agent implements the ReAct (Reasoning + Acting) pattern for web browser
navigation tasks using LangGraph's stateful graph workflow.

The agent follows a think->act->observe loop:
1. Reason: Use LLM to analyze current state and decide next action
2. Act: Execute the chosen browser action
3. Observe: Process results and update state

Uses ADK BaseAgent pattern for compatibility with to_a2a() and Docker builds.
"""

import json
import logging
from collections.abc import AsyncGenerator
from typing import Any

import uvicorn
from dotenv import load_dotenv
from google.adk.a2a.utils.agent_to_a2a import to_a2a
from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.genai import types
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()

from scenarios.web_browser.agents import create_agent_card, create_base_arg_parser

logger = logging.getLogger(__name__)


# ==============================================================================
# ReAct Prompt Template
# ==============================================================================


def build_react_prompt(
    task_description: str,
    current_snapshot: str,
) -> str:
    """
    Build a ReAct-style prompt for reasoning.

    This prompt guides the LLM to think step-by-step and choose appropriate
    actions based on the current state of the browser.
    """
    prompt = f"""You are a web automation agent using the ReAct pattern.

TASK: {task_description}

AVAILABLE TOOLS:

browser_click:
  Click on an element
  Parameters:
    - element: str (REQUIRED) - Human-readable element description
    - ref: str (REQUIRED) - Snapshot reference (e.g., s8)

browser_type:
  Type text into an element
  Parameters:
    - element: str (REQUIRED) - Human-readable element description
    - ref: str (REQUIRED) - Snapshot reference (e.g., s8)
    - text: str (REQUIRED) - Text to type

browser_select:
  Select an option from a dropdown
  Parameters:
    - element: str (REQUIRED) - Human-readable element description
    - ref: str (REQUIRED) - Snapshot reference (e.g., s8)
    - value: str (REQUIRED) - Value to select

browser_scroll:
  Scroll the page
  Parameters:
    - direction: str (REQUIRED) - Direction to scroll (up/down)

browser_close:
  Close the browser and end the task
  Parameters: none

CURRENT PAGE SNAPSHOT:
{current_snapshot}

Follow the ReAct pattern:
1. THINK: Analyze the current state and reason about what to do next
2. ACT: Choose ONE tool to execute with appropriate parameters

You MUST respond with valid JSON in the following format wrapped in <json></json> tags:

<json>
{{
  "thought": "Your step-by-step reasoning about what to do next",
  "tool": "tool_name",
  "params": {{
    "param1": "value1",
    "param2": "value2"
  }}
}}
</json>

Important guidelines:
- Most interactive tools require BOTH "element" (description) and "ref" (snapshot reference like "s8")
- Always look at the snapshot to find the correct ref for the element you want to interact with
- Think carefully about which action will make progress toward the task goal
- Use "browser_close" when the task is complete
- Make sure your JSON is properly formatted with double quotes

Now, think step-by-step and decide what to do next:"""

    return prompt


# ==============================================================================
# LangGraph ReAct Agent (ADK BaseAgent)
# ==============================================================================


class LangGraphReActAgent(BaseAgent):
    """
    LangGraph-based ReAct agent using ADK BaseAgent pattern.

    Implements ReAct (Reasoning + Acting) pattern with LangChain/LangGraph
    for web browser navigation tasks. Compatible with to_a2a() wrapper.
    """

    name: str = "langgraph_react_agent"
    description: str = "LangGraph ReAct agent for web browser navigation"

    def _get_snapshot_text(self, ctx: InvocationContext) -> str:
        """Extract text content from the latest user message."""
        if ctx.user_content is None:
            return ""

        parts = ctx.user_content.parts
        if parts is None:
            return ""

        text_parts = []
        for part in parts:
            if hasattr(part, "text") and part.text:
                text_parts.append(part.text)

        return "".join(text_parts)

    def _extract_task(self, text: str) -> str:
        """Extract task description from message text."""
        if "TASK:" in text:
            lines = text.split("TASK:")[1].split("\n")
            return lines[0].strip() if lines else "Complete the web task"
        return "Complete the web task"

    def _extract_snapshot(self, text: str) -> str:
        """Extract page snapshot from message text."""
        if "CURRENT PAGE SNAPSHOT:" in text:
            snapshot = text.split("CURRENT PAGE SNAPSHOT:")[1]
            if "[Snapshot truncated" in snapshot:
                snapshot = snapshot.split("[Snapshot truncated")[0]
            return snapshot.strip()
        return text  # Use full text as snapshot if no marker

    def _build_response(self, thought: str, tool: str, params: dict) -> str:
        """Build <json>{"thought", "tool", "params"}</json> response string."""
        response_dict = {
            "thought": thought,
            "tool": tool,
            "params": params,
        }
        return f"<json>{json.dumps(response_dict)}</json>"

    def _call_llm(self, prompt: str) -> dict[str, Any]:
        """
        Call LangChain LLM with ReAct prompt and parse response.

        Returns dict with 'thought', 'tool', 'params' keys.
        """
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            temperature=0.0,
            top_p=0.95,
        )

        response = llm.invoke([HumanMessage(content=prompt)])
        response_text = response.content

        # Ensure response_text is a string
        if not isinstance(response_text, str):
            response_text = str(response_text)

        logger.info(f"LLM Response:\n{response_text[:500]}...")

        # Parse response
        try:
            if "<json>" in response_text and "</json>" in response_text:
                json_str = response_text.split("<json>")[1].split("</json>")[0].strip()
                parsed = json.loads(json_str)
            else:
                parsed = json.loads(response_text)

            return {
                "thought": parsed.get("thought", "No thought provided"),
                "tool": parsed.get("tool", "browser_close"),
                "params": parsed.get("params", {}),
            }

        except (json.JSONDecodeError, KeyError, IndexError) as e:
            logger.error(f"Failed to parse LLM response: {e}")
            return {
                "thought": f"Error parsing response: {e}",
                "tool": "browser_close",
                "params": {},
            }

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        """
        Core agent logic: extract snapshot, call LLM, yield response Event.

        Args:
            ctx: Invocation context with session, user content, and event metadata

        Yields:
            Event with content containing <json>{"thought", "tool", "params"}</json>
        """
        # Extract message text
        message_text = self._get_snapshot_text(ctx)
        logger.info(f"LangGraph agent received message: {message_text[:200]}...")

        # Parse task and snapshot
        task = self._extract_task(message_text)
        snapshot = self._extract_snapshot(message_text)

        logger.info(f"Task: {task}")
        logger.info(f"Snapshot length: {len(snapshot)} chars")

        # Build ReAct prompt and call LLM
        prompt = build_react_prompt(task, snapshot)
        result = self._call_llm(prompt)

        # Build response
        response = self._build_response(
            result["thought"], result["tool"], result["params"]
        )

        logger.info(f"LangGraph agent response: {response[:200]}...")

        yield Event(
            invocation_id=ctx.invocation_id,
            author=self.name,
            branch=ctx.branch,
            content=types.Content(role="model", parts=[types.Part(text=response)]),
        )


# ==============================================================================
# Main
# ==============================================================================


def main() -> None:
    """Run the LangGraph ReAct browser navigation white agent."""
    parser = create_base_arg_parser(
        "Run the LangGraph ReAct-based A2A browser navigation white agent."
    )
    args = parser.parse_args()

    agent = LangGraphReActAgent()
    agent_card = create_agent_card(
        name="langgraph_react_agent",
        description="A ReAct-based web browser navigation agent using LangGraph.",
        host=args.host,
        port=args.port,
        card_url=args.card_url,
    )

    a2a_app = to_a2a(agent, agent_card=agent_card)
    print(f"Starting white agent (langgraph) on {args.host}:{args.port}")
    uvicorn.run(a2a_app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()

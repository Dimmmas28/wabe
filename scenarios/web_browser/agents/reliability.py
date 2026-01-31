"""
Deterministic Replay Agent for Benchmark Reliability Testing.

This agent replays a hardcoded 7-step action sequence for a SPECIFIC task:

    Website: https://sl.se/
    Task: "Find the travel time from T-Centralen to Artipelag using the SL.se journey planner."
    Scenario: scenarios/web_browser/scenario_reliability.toml

The agent does NOT use LLM calls - it dynamically extracts ref values from
accessibility snapshots via regex pattern matching, then replays predetermined actions.

Use cases:
- Benchmark consistency testing (isolates green agent behavior from LLM variability)
- CI/CD validation without API costs
- Debugging the evaluation framework

NOTE: This agent ONLY works with the specific task above. It is NOT a general-purpose
agent for leaderboard participation. For leaderboard agents, see adk_default.py.
"""

import json
import logging
import re
from collections.abc import AsyncGenerator

import uvicorn
from google.adk.a2a.utils.agent_to_a2a import to_a2a
from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.genai import types
from pydantic import Field

from scenarios.web_browser.agents import create_agent_card, create_base_arg_parser

logger = logging.getLogger(__name__)


class ReliabilityAgent(BaseAgent):
    """
    Deterministic replay agent for benchmark reliability testing.

    Replays a hardcoded 7-step action sequence for the SL.se travel time task
    (T-Centralen → Artipelag). No LLM calls - extracts refs via regex matching.

    Only works with scenario_reliability.toml. Not for leaderboard use.
    """

    name: str = "reliability_agent"
    description: str = (
        "Deterministic replay agent for SL.se benchmark reliability testing"
    )
    actions: list[dict] = Field(default_factory=list)

    def __init__(self, **kwargs):
        """Initialize the agent and populate the 7-step action sequence."""
        super().__init__(**kwargs)

        # Define the 7-step SL.se travel time action sequence
        self.actions = [
            {
                "element_pattern": r"Godkänn alla kakor",
                "tool": "browser_click",
                "thought": "Accept cookie consent",
                "params_template": {"ref": None},
            },
            {
                "element_pattern": r"[Ff]rån",
                "tool": "browser_type",
                "thought": "Type departure station",
                "params_template": {"ref": None, "text": "T-Centralen"},
            },
            {
                "element_pattern": r"T-Centralen \(Stockholm\)",
                "tool": "browser_click",
                "thought": "Select T-Centralen from suggestions",
                "params_template": {"ref": None},
            },
            {
                "element_pattern": r"[Tt]ill",
                "tool": "browser_type",
                "thought": "Type destination",
                "params_template": {"ref": None, "text": "Artipelag"},
            },
            {
                "element_pattern": r"Artipelag.*[Vv]ärmd",
                "tool": "browser_click",
                "thought": "Select Artipelag from suggestions",
                "params_template": {"ref": None},
            },
            {
                "element_pattern": r"Sök",
                "tool": "browser_click",
                "thought": "Click search button",
                "params_template": {"ref": None},
            },
            {
                "element_pattern": None,
                "tool": "browser_close",
                "thought": "Task complete, closing browser",
                "params_template": {},
            },
        ]

    def _get_step_index(self, ctx: InvocationContext) -> int:
        """
        Determine current step by counting prior model events in session.

        Args:
            ctx: Invocation context with session events

        Returns:
            Zero-based step index (0-6 for 7 steps)
        """
        count = 0
        for event in ctx.session.events:
            if event.author == self.name:
                count += 1
        return count

    def _extract_ref(self, snapshot_text: str, element_pattern: str) -> str | None:
        """
        Extract ref value from accessibility snapshot by matching element description.

        Searches for lines matching element_pattern and extracts [ref=sXX] value.
        Uses regex: pattern matching element_pattern followed by [ref=<value>].

        Args:
            snapshot_text: Full accessibility snapshot text
            element_pattern: Regex pattern to match element description

        Returns:
            The ref value string (e.g., "s12") or None if not found
        """
        if not snapshot_text:
            return None

        # Search for the pattern followed by a ref tag on the same line
        # Use IGNORECASE to handle both "Från" and "från", etc.
        # Use MULTILINE to match ^ and $ per line, not DOTALL which would match across lines
        pattern = rf"{element_pattern}.*?\[ref=([^\]]+)\]"
        match = re.search(pattern, snapshot_text, re.IGNORECASE | re.MULTILINE)

        if match:
            return match.group(1)

        return None

    def _get_snapshot_text(self, ctx: InvocationContext) -> str:
        """
        Extract text content from the latest user message.

        Iterates through ctx.user_content.parts, concatenates text parts,
        ignores image/file parts.

        Args:
            ctx: Invocation context with user_content

        Returns:
            Concatenated text from user message parts
        """
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

    def _build_response(self, thought: str, tool: str, params: dict) -> str:
        """
        Build <json>{"thought", "tool", "params"}</json> response string.

        Args:
            thought: Agent thought text
            tool: Tool name to invoke
            params: Tool parameters dict

        Returns:
            Formatted response string: '<json>{"thought": "...", "tool": "...", "params": {...}}</json>'
        """
        response_dict = {
            "thought": thought,
            "tool": tool,
            "params": params,
        }
        return f"<json>{json.dumps(response_dict)}</json>"

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        """
        Core agent logic: determine current step, extract ref from snapshot, yield Event.

        Counts prior model events in ctx.session.events to determine current step index.
        Extracts snapshot text from ctx.user_content (latest user message).
        Pattern-matches element description to find ref value.
        Yields a single Event with <json> response.

        Args:
            ctx: Invocation context with session, user content, and event metadata

        Yields:
            Event with content containing <json>{"thought", "tool", "params"}</json>
        """
        step_index = self._get_step_index(ctx)
        logger.info(f"Reliability agent step {step_index + 1}/{len(self.actions)}")

        # Safety: if past all steps, close browser
        if step_index >= len(self.actions):
            logger.info("All steps completed, sending browser_close")
            response = self._build_response("All steps completed", "browser_close", {})
            yield Event(
                invocation_id=ctx.invocation_id,
                author=self.name,
                branch=ctx.branch,
                content=types.Content(role="model", parts=[types.Part(text=response)]),
            )
            return

        action = self.actions[step_index]

        # Last step (browser_close) needs no ref extraction
        if action["element_pattern"] is None:
            response = self._build_response(
                action["thought"], action["tool"], action["params_template"]
            )
        else:
            snapshot_text = self._get_snapshot_text(ctx)
            ref = self._extract_ref(snapshot_text, action["element_pattern"])

            if ref is None:
                logger.warning(
                    f"Element not found for step {step_index}: {action['element_pattern']}"
                )
                # Request fresh snapshot as fallback
                response = self._build_response(
                    f"Element not found: {action['element_pattern']}, requesting snapshot",
                    "browser_snapshot",
                    {},
                )
            else:
                params = {**action["params_template"], "ref": ref}
                response = self._build_response(
                    action["thought"], action["tool"], params
                )

        yield Event(
            invocation_id=ctx.invocation_id,
            author=self.name,
            branch=ctx.branch,
            content=types.Content(role="model", parts=[types.Part(text=response)]),
        )


def main() -> None:
    """
    CLI entry point: create ReliabilityAgent, wrap with to_a2a(), serve via uvicorn.

    Uses create_base_arg_parser() and create_agent_card() from agents __init__.
    """
    parser = create_base_arg_parser("Run the deterministic reliability replay agent.")
    args = parser.parse_args()

    agent = ReliabilityAgent()
    agent_card = create_agent_card(
        name="reliability_agent",
        description="Deterministic replay agent for SL.se benchmark reliability testing",
        host=args.host,
        port=args.port,
        card_url=args.card_url,
    )

    a2a_app = to_a2a(agent, agent_card=agent_card)
    print(f"Starting reliability agent on {args.host}:{args.port}")
    uvicorn.run(a2a_app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()

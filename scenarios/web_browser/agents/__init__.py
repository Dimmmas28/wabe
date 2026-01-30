"""
White Agent Registry - Pluggable directory convention for white agents.

Each agent is a standalone Python file with a main() entry point that serves
an A2A-compatible agent via uvicorn. Agents share the create_agent_card()
helper for consistent agent card creation.

Available agents:
    - adk_default: Google ADK Agent with Gemini Flash (original white agent)
    - reliability: Deterministic replay agent for benchmark reliability testing
    - langgraph: LangGraph ReAct agent (WIP - needs refactor for Docker/leaderboard)
"""

import argparse

from a2a.types import AgentCapabilities, AgentCard


def create_agent_card(
    name: str,
    description: str,
    host: str,
    port: int,
    card_url: str | None = None,
    input_modes: list[str] | None = None,
    output_modes: list[str] | None = None,
) -> AgentCard:
    """
    Create a standard agent card for a white agent.

    Args:
        name: Agent name identifier
        description: Human-readable description of the agent
        host: Host the agent is bound to
        port: Port the agent is bound to
        card_url: Optional external URL for the agent card
        input_modes: Input modes (default: ["text", "image"])
        output_modes: Output modes (default: ["text"])

    Returns:
        AgentCard configured for this agent
    """
    return AgentCard(
        name=name,
        description=description,
        url=card_url or f"http://{host}:{port}/",
        version="1.0.0",
        default_input_modes=input_modes or ["text", "image"],
        default_output_modes=output_modes or ["text"],
        capabilities=AgentCapabilities(streaming=True),
        skills=[],
    )


def create_base_arg_parser(description: str) -> argparse.ArgumentParser:
    """
    Create a standard argument parser for white agents.

    Args:
        description: Description for the argument parser

    Returns:
        ArgumentParser with --host, --port, --card-url arguments
    """
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "--host", type=str, default="127.0.0.1", help="Host to bind the server"
    )
    parser.add_argument(
        "--port", type=int, default=9019, help="Port to bind the server"
    )
    parser.add_argument(
        "--card-url", type=str, help="External URL to provide in the agent card"
    )
    return parser

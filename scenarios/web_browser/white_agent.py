"""
White Agent for Web Browser Navigation Tasks

This agent receives browser state (HTML, task description) from the green agent
and returns navigation actions (click, type, select, etc.).

Follows the Google ADK pattern from AgentBeats tutorial (scenarios/debate/debater.py).
"""

import argparse

import uvicorn
from dotenv import load_dotenv

load_dotenv()

from a2a.types import AgentCapabilities, AgentCard
from google.adk.a2a.utils.agent_to_a2a import to_a2a
from google.adk.agents import Agent


def browser_agent_card(host: str, port: int, card_url: str = None) -> AgentCard:
    """Create the agent card for the browser navigation agent."""
    return AgentCard(
        name="browser_agent",
        description="A web browser navigation agent that helps complete web tasks by analyzing HTML and providing navigation actions.",
        url=card_url or f"http://{host}:{port}/",
        version="1.0.0",
        default_input_modes=["text", "image"],
        default_output_modes=["text"],
        capabilities=AgentCapabilities(streaming=True),
        skills=[],
    )


def main():
    parser = argparse.ArgumentParser(
        description="Run the A2A browser navigation white agent."
    )
    parser.add_argument(
        "--host", type=str, default="127.0.0.1", help="Host to bind the server"
    )
    parser.add_argument(
        "--port", type=int, default=9019, help="Port to bind the server"
    )
    parser.add_argument(
        "--card-url", type=str, help="External URL to provide in the agent card"
    )
    args = parser.parse_args()

    # Create the browser navigation agent
    # Reusing the same model and instruction pattern from src/white_agent/default_agent.py
    root_agent = Agent(
        name="browser_agent",
        model="gemini-2.5-flash",  # Using flash model for faster responses
        description="A web browser navigation agent that helps complete web tasks.",
        instruction="""You are a helpful web automation agent.
Your task is to help complete web navigation and interaction tasks.

Analyze the information provided and choose the appropriate action to progress toward completing the task.""",
    )

    # Create agent card
    agent_card = browser_agent_card(args.host, args.port, args.card_url)

    # Convert to A2A protocol and run
    a2a_app = to_a2a(root_agent, agent_card=agent_card)

    print(f"Starting white agent (browser_agent) on {args.host}:{args.port}")
    uvicorn.run(a2a_app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()

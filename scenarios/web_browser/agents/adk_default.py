"""
Default White Agent for Web Browser Navigation Tasks (Google ADK).

This agent receives browser state (accessibility snapshot, screenshot, task description)
from the green agent and returns navigation actions (click, type, select, etc.).

Uses Google ADK Agent with Gemini Flash model for fast, deterministic responses.

Environment Variables:
    PURPLE_AGENT_MODEL: Model to use (default: gemini-2.5-flash)
                        Options: gemini-2.5-flash, gemini-2.5-pro
"""

import os

import uvicorn
from dotenv import load_dotenv

load_dotenv()

# Model configuration - can be overridden via environment variable
DEFAULT_MODEL = "gemini-2.5-flash"
AGENT_MODEL = os.getenv("PURPLE_AGENT_MODEL", DEFAULT_MODEL)

from google.adk.a2a.utils.agent_to_a2a import to_a2a
from google.adk.agents import Agent
from google.genai import types

from scenarios.web_browser.agents import (
    RetryGemini,
    create_agent_card,
    create_base_arg_parser,
)


def main():
    """Run the default ADK browser navigation white agent."""
    parser = create_base_arg_parser(
        "Run the default A2A browser navigation white agent (Google ADK)."
    )
    args = parser.parse_args()

    # Create model with retry wrapper for rate limit handling
    # Model can be configured via PURPLE_AGENT_MODEL environment variable
    print(f"Using model: {AGENT_MODEL}")
    model = RetryGemini(
        model=AGENT_MODEL,
        max_retries=5,
        base_delay=2.0,
        max_delay=60.0,
    )

    # Create the browser navigation agent
    root_agent = Agent(
        name="browser_agent",
        model=model,
        description="A web browser navigation agent that helps complete web tasks.",
        instruction="""You are a helpful web automation agent.
Your task is to help complete web navigation and interaction tasks.

Analyze the information provided and choose the appropriate action to progress toward completing the task.

IMPORTANT: If you encounter blockers that cannot be bypassed, call "browser_close":
- CAPTCHA/reCAPTCHA challenges (cannot solve programmatically)
- Login walls that keep reappearing after closing
- Access denied (403) or authentication required
- Stuck in a loop (3+ similar actions without progress)

Do not navigate to other websites to work around login walls.""",
        generate_content_config=types.GenerateContentConfig(
            temperature=0.0,
            top_p=0.0,
            top_k=1,
            seed=42,
        ),
    )

    # Create agent card
    agent_card = create_agent_card(
        name="browser_agent",
        description="A web browser navigation agent that helps complete web tasks by analyzing HTML and providing navigation actions.",
        host=args.host,
        port=args.port,
        card_url=args.card_url,
    )

    # Convert to A2A protocol and run
    a2a_app = to_a2a(root_agent, agent_card=agent_card)

    print(f"Starting white agent (adk_default) on {args.host}:{args.port}")
    uvicorn.run(a2a_app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()

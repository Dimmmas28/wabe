"""
ReAct White Agent for Web Browser Navigation Tasks (Google ADK).

This agent receives browser state (accessibility snapshot, screenshot, task description)
from the green agent and returns navigation actions (click, type, select, etc.).

Uses Google ADK Agent with Gemini Flash model and Observe→Think→Act reasoning methodology.
"""

import uvicorn
from dotenv import load_dotenv

load_dotenv()

from google.adk.a2a.utils.agent_to_a2a import to_a2a
from google.adk.agents import Agent
from google.genai import types

from scenarios.web_browser.agents import (
    RetryGemini,
    create_agent_card,
    create_base_arg_parser,
)

REACT_INSTRUCTION = """You are a ReAct (Reason + Act) web automation agent.

For each step, follow this methodology:

OBSERVE: What do you see on the current page?
- Identify key interactive elements relevant to the task
- Note the current state (forms, buttons, links, inputs)
- Recognize what has changed since the last action
- Check for blockers: login walls, CAPTCHAs, access denied pages

THINK: What action will make progress toward the goal?
- Analyze which element to interact with
- Consider the task requirements and current page state
- Choose the most direct action to advance
- Detect if you are stuck in a loop (repeating similar actions without progress)

ACT: Execute one precise action.

IMPORTANT - Recognize when to stop:
If you encounter ANY of these blockers, call "browser_close" immediately:
- CAPTCHA or reCAPTCHA challenges (cannot be solved programmatically)
- Login/sign-in walls that repeatedly reappear after closing
- Access denied (403) or authentication required pages
- Repeated failed attempts (3+ tries) at the same action with no progress
- Site requires account creation to proceed

Do NOT:
- Keep trying to solve CAPTCHAs
- Navigate to different websites to work around login walls
- Repeatedly close the same popup if it keeps reappearing

When blocked, set your thought to explain why the task cannot be completed (e.g., "Site requires login which cannot be bypassed") and call browser_close.

Write your observation and reasoning in the "thought" field. Follow the response format specified in the user message."""


def main():
    """Run the ReAct ADK browser navigation white agent."""
    parser = create_base_arg_parser(
        "Run the ReAct A2A browser navigation white agent (Google ADK)."
    )
    args = parser.parse_args()

    # Create model with retry wrapper for rate limit handling
    model = RetryGemini(
        model="gemini-2.5-flash",
        max_retries=5,
        base_delay=2.0,
        max_delay=60.0,
    )

    # Create the browser navigation agent
    root_agent = Agent(
        name="browser_agent_react",
        model=model,
        description="A ReAct web browser agent that uses Observe→Think→Act reasoning.",
        instruction=REACT_INSTRUCTION,
        generate_content_config=types.GenerateContentConfig(
            temperature=0.0,
            top_p=0.0,
            top_k=1,
            seed=42,
        ),
    )

    # Create agent card
    agent_card = create_agent_card(
        name="browser_agent_react",
        description="A ReAct web browser navigation agent that uses Observe→Think→Act reasoning to complete web tasks.",
        host=args.host,
        port=args.port,
        card_url=args.card_url,
    )

    # Convert to A2A protocol and run
    a2a_app = to_a2a(root_agent, agent_card=agent_card)

    print(f"Starting white agent (react_adk) on {args.host}:{args.port}")
    uvicorn.run(a2a_app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()

"""
ReAct White Agent for Web Browser Navigation Tasks (Google ADK).

This agent receives browser state (accessibility snapshot, screenshot, task description)
from the green agent and returns navigation actions (click, type, select, etc.).

Uses Google ADK Agent with Gemini Flash model and Observe→Think→Act reasoning methodology.

Environment Variables:
    PURPLE_AGENT_MODEL: Model to use (default: gemini-2.5-flash)
                        Options: gemini-2.5-flash, gemini-2.5-pro
"""

import logging
import os
from typing import Optional

import uvicorn
from dotenv import load_dotenv

load_dotenv()

# Model configuration - can be overridden via environment variable
DEFAULT_MODEL = "gemini-2.5-flash"
AGENT_MODEL = os.getenv("PURPLE_AGENT_MODEL", DEFAULT_MODEL)

from google.adk.a2a.utils.agent_to_a2a import to_a2a
from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import types

from scenarios.web_browser.agents import (
    RetryGemini,
    create_agent_card,
    create_base_arg_parser,
)

logger = logging.getLogger(__name__)

REACT_INSTRUCTION = """You are a ReAct (Reason + Act) web automation agent.

## CRITICAL: READ THE USER MESSAGE CAREFULLY

The user message contains:
1. TASK DESCRIPTION - Your goal. Remember it throughout the conversation.
2. RESPONSE FORMAT - Follow it EXACTLY. Do not invent your own format.
3. AVAILABLE TOOLS - Use only these tools with correct parameters.
4. PAGE SNAPSHOT - Current state of the webpage.

You must be SELF-SUFFICIENT. The judge will not remind you of the task or format.

## METHODOLOGY

On each step, follow this reasoning process:

### OBSERVE
- Study the CURRENT PAGE SNAPSHOT - what elements exist?
- Find interactive elements with [ref=...] tags
- Has the page changed since your last action?
- Any blockers (CAPTCHAs, login walls, access denied)?

### THINK
- What is my goal? (from the TASK in first message)
- What progress has been made?
- What is the most direct next action?

### LOOP DETECTION
Before acting, check:
- Have I done this EXACT action before?
- Have I tried this approach 2+ times without success?

If YES: try a COMPLETELY DIFFERENT approach or call "browser_close".

### ACT
Choose ONE action. Output using the EXACT format specified in the user message.

## STOPPING CONDITIONS

Call "finish" when:
- Task objective is visibly achieved
- Requested information is displayed

Call "browser_close" when:
- CAPTCHA/reCAPTCHA appears
- Access denied / 403 / regional block
- Login wall that cannot be bypassed
- Same action failed 3+ times
"""


def strip_images_from_history(
    callback_context: CallbackContext, llm_request: LlmRequest
) -> Optional[LlmResponse]:
    """
    Before-model callback that strips images from historical messages to reduce token usage.

    Problem: With conversation history, each step accumulates ~30K tokens. By step 20,
    we're sending 600K+ tokens per request, causing TPM quota exhaustion.

    Solution: Keep images only in the LAST user message (current state). Historical
    messages are summarized as "[image was sent]" - the agent still sees what actions
    it took but doesn't re-process old screenshots.

    This reduces token growth from O(n * image_size) to O(n * text_only + image_size).

    Args:
        callback_context: Callback context (unused)
        llm_request: The LLM request with conversation contents

    Returns:
        None to continue with modified request, or LlmResponse to skip model call
    """
    # Note: ADK calls this with keyword arguments, but we define positional params
    # to satisfy the type checker. Both work since Python allows either.
    request = llm_request  # Alias for readability
    if not request.contents:
        return None

    # Find the last user message index
    last_user_idx = -1
    for i, content in enumerate(request.contents):
        if content.role == "user":
            last_user_idx = i

    # Strip images from all messages except the last user message
    for i, content in enumerate(request.contents):
        if i == last_user_idx:
            # Keep the last user message intact (current screenshot needed)
            continue

        if not content.parts:
            continue

        # Filter out image parts, replace with placeholder text
        new_parts = []
        had_image = False
        for part in content.parts:
            # Check if this is an image part (inline_data with image mime type)
            if hasattr(part, "inline_data") and part.inline_data:
                if (
                    hasattr(part.inline_data, "mime_type")
                    and part.inline_data.mime_type
                ):
                    if part.inline_data.mime_type.startswith("image/"):
                        had_image = True
                        continue  # Skip this image part
            new_parts.append(part)

        # Add a placeholder if we removed images
        if had_image:
            new_parts.append(types.Part(text="[screenshot was shown]"))

        content.parts = new_parts

    return None  # Continue with modified request


def main():
    """Run the ReAct ADK browser navigation white agent."""
    parser = create_base_arg_parser(
        "Run the ReAct A2A browser navigation white agent (Google ADK)."
    )
    args = parser.parse_args()

    # Create model with retry wrapper for rate limit handling
    # Model can be configured via PURPLE_AGENT_MODEL environment variable
    # Using 60s base delay to properly wait for TPM quota reset (1 minute window)
    print(f"Using model: {AGENT_MODEL}")
    model = RetryGemini(
        model=AGENT_MODEL,
        max_retries=5,
        base_delay=60.0,
        max_delay=120.0,
    )

    # Create the browser navigation agent
    # Uses before_model_callback to strip images from historical messages, reducing TPM usage.
    # The agent keeps full conversation history for context but only processes the current screenshot.
    root_agent = Agent(
        name="browser_agent_react",
        model=model,
        description="A ReAct web browser agent that uses Observe→Think→Act reasoning.",
        instruction=REACT_INSTRUCTION,
        before_model_callback=strip_images_from_history,  # Strips old screenshots to save tokens
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

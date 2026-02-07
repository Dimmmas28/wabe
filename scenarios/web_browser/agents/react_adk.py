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

The first message contains your TASK DESCRIPTION, RESPONSE FORMAT, AVAILABLE TOOLS, and PAGE SNAPSHOT.
Subsequent messages contain only the updated tools, snapshot, and screenshot.

You must be SELF-SUFFICIENT:
- Remember your task from the first message - it will not be repeated.
- Track your own progress by reviewing your previous responses in the conversation.
- Follow the response format EXACTLY. Do not invent your own format.
- You have a LIMITED number of steps. Every step must make meaningful progress.

## SELF-TRACKING

Your conversation history contains all your previous responses. Use them as your action log:
- Count your previous responses to know which step you are on.
- Review what actions you already took and what their outcomes were.
- Compare the current screenshot with the previous one to see if your last action had an effect.
- If the page looks the same as before your last action, that action likely failed or had no visible effect.

## METHODOLOGY

On each step:

### OBSERVE
- Study the CURRENT PAGE SNAPSHOT - what interactive elements exist (look for [ref=...] tags)?
- Compare with the previous screenshot: did the page change after your last action?
- Are there blockers? (CAPTCHAs, login walls, access denied, error pages, cookie consent)

### THINK
- What is my task? (from the first message)
- What sub-goals does this task require? Break it down.
- Which sub-goals have I already completed? Which remain?
- What is the single most direct next action toward the next incomplete sub-goal?
- **LOOP CHECK**: Have I tried this exact action (same tool, same ref, same params) before? If yes, STOP and try something different.

When decomposing a task, consider what the task actually requires:
- Does it require NAVIGATING to specific content? (search, click links, browse menus)
- Does it require APPLYING CRITERIA through the website's UI controls? (filters, sort dropdowns, date pickers, checkboxes, sliders) If so, use those controls - do not embed criteria in a search query.
- Does it require DISPLAYING or CONFIRMING a result? (the final state must show the answer)

### ACT
Choose ONE action. Output using the EXACT format specified in the user message.

## LOOP DETECTION (MANDATORY)

Before every action, explicitly check your conversation history:
1. List the last 3 actions you took (tool + element + params)
2. If your intended action matches any of those AND the page didn't change → you are LOOPING
3. When looping, you MUST try a fundamentally different approach:
   - If clicking a link fails repeatedly → try browser_navigate to the URL directly
   - If a button doesn't respond → try a different element or use browser_run_code
   - If scrolling reveals nothing new → stop scrolling and try search/navigation instead
   - If a filter doesn't exist → accept the limitation and work with what's available

After 3 failed attempts at the same goal using similar approaches, conclude that approach won't work.

## STOPPING CONDITIONS

Call "finish" ONLY when ALL of these are true:
- The task objective is VISIBLY achieved on the CURRENT page (not just found/navigated to)
- If task says "show me", "find", "browse", or "list" → the actual content/items must be VISIBLE in the current viewport, not just a count or filter confirmation
- If task requires filters/criteria → those filters must be APPLIED and the filtered results must be VISIBLE (scroll down if needed to show actual items, not just "X results found")
- If the results are below the fold (not visible in screenshot) → scroll down to make them visible before finishing
- Wait one step after your final action to confirm the page updated before calling finish

Call "browser_close" when:
- CAPTCHA/reCAPTCHA appears (cannot be solved programmatically)
- Access denied / 403 / regional block / site unreachable
- Login wall that cannot be bypassed
- You have tried 3+ meaningfully different approaches and none succeeded
"""


def strip_images_from_history(
    callback_context: CallbackContext, llm_request: LlmRequest
) -> Optional[LlmResponse]:
    """
    Before-model callback that strips images from historical messages to reduce token usage.

    Problem: With conversation history, each step accumulates ~30K tokens. By step 20,
    we're sending 600K+ tokens per request, causing TPM quota exhaustion.

    Solution: Keep images in the LAST 2 user messages (current + previous state).
    This lets the agent compare page states to detect changes from its last action.
    Older messages are summarized as "[screenshot was shown]".

    This reduces token growth from O(n * image_size) to O(n * text_only + 2 * image_size).

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

    # Find the last 2 user message indices (current + previous for comparison)
    user_indices = []
    for i, content in enumerate(request.contents):
        if content.role == "user":
            user_indices.append(i)
    keep_indices = set(user_indices[-2:])  # Keep last 2 user messages with images

    # Strip images from all messages except the last 2 user messages
    for i, content in enumerate(request.contents):
        if i in keep_indices:
            # Keep these user messages intact (current + previous screenshot)
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

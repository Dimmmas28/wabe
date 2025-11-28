"""
Browser Judge - Green Agent for evaluating web automation agents.

This agent evaluates a white agent's ability to perform web browsing tasks
by orchestrating browser interactions and coordinating with the white agent.
"""

import argparse
import asyncio
import contextlib
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

import uvicorn
# A2A framework
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore, TaskUpdater
from a2a.types import (AgentCapabilities, AgentCard, AgentSkill, FilePart,
                       FileWithBytes, Part, TaskState, TextPart)
from a2a.utils import new_agent_text_message
from dotenv import load_dotenv

# AgentBeats framework
from agentbeats.green_executor import GreenAgent, GreenExecutor
from agentbeats.models import EvalRequest, EvalResult
from agentbeats.tool_provider import ToolProvider

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Existing WABE components
from src.shared.browser_agent import BrowserAgent
from src.shared.response_parser import parse_white_agent_response

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class BrowserJudge(GreenAgent):
    """
    Green agent that evaluates white agents on web browsing tasks.

    This agent:
    1. Receives an evaluation request with white agent URL and task config
    2. Launches a browser and navigates to the target website
    3. Sends HTML + task description to white agent
    4. Receives action from white agent
    5. Executes action in browser
    6. Repeats until task completes or max steps reached
    7. Returns evaluation result
    """

    def __init__(self):
        """Initialize the Browser Judge agent."""
        self._required_roles = ["white_agent"]
        self._required_config_keys = ["task_id", "website", "task", "max_steps"]
        self._tool_provider = ToolProvider()
        logger.info("BrowserJudge initialized")

    def validate_request(self, request: EvalRequest) -> tuple[bool, str]:
        """
        Validate that the evaluation request has all required fields.

        Args:
            request: The evaluation request to validate

        Returns:
            Tuple of (is_valid, message)
        """
        # Check for required participant roles
        missing_roles = set(self._required_roles) - set(request.participants.keys())
        if missing_roles:
            return False, f"Missing required participant roles: {missing_roles}"

        # Check for required configuration keys
        missing_config = set(self._required_config_keys) - set(request.config.keys())
        if missing_config:
            return False, f"Missing required config keys: {missing_config}"

        logger.info(f"Request validation passed: {request}")
        return True, "ok"

    async def run_eval(self, req: EvalRequest, updater: TaskUpdater) -> None:
        """
        Run the browser task evaluation.

        Args:
            req: The evaluation request containing participants and config
            updater: TaskUpdater for sending status updates and artifacts
        """
        logger.info(f"Starting browser evaluation: {req}")

        # Extract configuration
        white_agent_url = str(req.participants["white_agent"])
        task_id = req.config["task_id"]
        website = req.config["website"]
        task_description = req.config["task"]
        max_steps = int(req.config["max_steps"])
        level = req.config.get("level", "unknown")

        await updater.update_status(
            TaskState.working,
            new_agent_text_message(f"Starting evaluation for task {task_id}"),
        )

        # Initialize browser agent
        # Use headless mode in Docker (when HEADLESS env var is set)
        # Default to False for local development to see browser
        headless = os.getenv("HEADLESS", "false").lower() in ("true", "1", "yes")
        browser_agent = BrowserAgent(
            headless=headless, output_dir=f".output/browser_eval_{task_id}"
        )

        success = False
        step_count = 0
        thoughts: list[str] = []
        error_message = None

        try:
            # Start browser and navigate to website
            logger.info(f"Starting browser and navigating to {website}")
            await updater.update_status(
                TaskState.working,
                new_agent_text_message(f"Opening browser at {website}"),
            )
            await browser_agent.start(website)

            # Prepare initial prompt for white agent
            initial_prompt = f"""You are a web automation agent. Your task is:

TASK: {task_description}

You are currently on the website: {website}

AVAILABLE TOOLS:
1. click - Click on an element
   Parameters: {{"selector": "CSS selector or XPath"}}

2. type - Type text into an input element
   Parameters: {{"selector": "CSS selector", "text": "text to type"}}

3. select - Select an option from a dropdown
   Parameters: {{"selector": "CSS selector", "value": "option value"}}

4. finish - Complete the task (no parameters needed)
   Parameters: {{}}

CRITICAL - RESPONSE FORMAT:
You MUST respond with JSON wrapped in <json></json> tags in this EXACT format:

<json>
{{
    "thought": "Your reasoning about what to do next",
    "tool": "tool_name",
    "params": {{"param_name": "param_value"}}
}}
</json>

EXAMPLES OF VALID RESPONSES:

Example 1 - Click action:
<json>
{{
    "thought": "I need to click the search button to proceed",
    "tool": "click",
    "params": {{"selector": "button#search"}}
}}
</json>

Example 2 - Type action:
<json>
{{
    "thought": "I should enter the search term in the input field",
    "tool": "type",
    "params": {{"selector": "input[name='query']", "text": "Las Vegas"}}
}}
</json>

Example 3 - Finish action:
<json>
{{
    "thought": "The task is complete, I have selected a theatre event",
    "tool": "finish",
    "params": {{}}
}}
</json>

IMPORTANT NOTES:
- Always wrap your JSON response in <json></json> tags
- The "thought" field should explain your reasoning
- The "tool" field must be one of: click, type, select, finish
- The "params" field must be a valid JSON object (use {{}} for finish)
- Do not include any text outside the <json></json> tags

CURRENT PAGE STATE:
"""

            # Main evaluation loop
            error_feedback = (
                None  # Track parse errors to provide feedback to white agent
            )

            for step in range(max_steps):
                step_count = step + 1
                logger.info(f"Starting step {step_count}/{max_steps}")

                # Add delay between steps to avoid rate limiting (except first step)
                if step > 0:
                    delay = 2  # 2 second delay between steps
                    logger.info(
                        f"Waiting {delay}s before next step to avoid rate limits..."
                    )
                    await asyncio.sleep(delay)

                await updater.update_status(
                    TaskState.working,
                    new_agent_text_message(f"Executing step {step_count}/{max_steps}"),
                )

                # Get current page HTML
                html = await browser_agent.get_html(cleaned=True, format="html")

                # Truncate HTML if too long (keep first 20000 chars)
                html_truncated = html[:20000]
                if len(html) > 20000:
                    html_truncated += "\n\n[HTML truncated for length...]"

                # Prepare multi-part message (text + image)
                parts = []

                # 1. Add text part with HTML and instructions
                if step == 0:
                    text_content = (
                        initial_prompt + f"\n\nCURRENT HTML:\n{html_truncated}"
                    )
                else:
                    # Include error feedback if previous response had parse errors
                    if error_feedback:
                        text_content = f"""ERROR IN PREVIOUS RESPONSE:
{error_feedback}

Please try again with the correct format. Remember to wrap your JSON in <json></json> tags.

CURRENT HTML:
{html_truncated}

What should we do next?"""
                        error_feedback = None  # Clear feedback after using it
                    else:
                        text_content = f"CURRENT HTML:\n{html_truncated}\n\nWhat should we do next?"

                parts.append(Part(root=TextPart(text=text_content)))

                # 2. Add image part (screenshot)
                screenshot_data = browser_agent.get_latest_screenshot_base64()
                if screenshot_data:
                    base64_string, screenshot_path = screenshot_data
                    logger.info(f"Attaching screenshot: {Path(screenshot_path).name}")

                    file_part = FilePart(
                        file=FileWithBytes(
                            bytes=base64_string,
                            mimeType="image/jpeg",
                            name=Path(screenshot_path).name,
                        )
                    )
                    parts.append(Part(root=file_part))
                else:
                    logger.warning("No screenshot available to attach")

                # Log what we're sending to white agent
                logger.info("=" * 60)
                logger.info(f"STEP {step_count}/{max_steps}: Sending to white agent")
                logger.info("=" * 60)
                logger.info(
                    f"Message parts: {len(parts)} (text + {'image' if screenshot_data else 'no image'})"
                )
                logger.info(
                    f"HTML length: {len(html)} chars (truncated to {len(html_truncated)} chars for agent)"
                )
                if screenshot_data:
                    logger.info(f"Screenshot: {Path(screenshot_path).name}")

                # Log first 500 chars of HTML for debugging
                logger.info(f"HTML preview (first 500 chars):\n{html[:500]}")

                # Save full HTML to file for detailed debugging (optional via env var)
                if os.getenv("SAVE_DEBUG_HTML", "false").lower() in (
                    "true",
                    "1",
                    "yes",
                ):
                    debug_html_path = (
                        f"{browser_agent.output_dir}/step_{step_count:03d}_input.html"
                    )
                    Path(debug_html_path).write_text(html)
                    logger.info(f"Saved full HTML to: {debug_html_path}")

                # Send to white agent and get response
                logger.info(f"Sending message to white agent at {white_agent_url}")
                try:
                    response_text = await self._tool_provider.talk_to_agent(
                        url=white_agent_url,
                        new_conversation=(step == 0),
                        parts=parts,
                    )

                    # Log full response (not truncated)
                    logger.info("=" * 60)
                    logger.info(
                        f"STEP {step_count}/{max_steps}: Response from white agent"
                    )
                    logger.info("=" * 60)
                    logger.info(f"Full response:\n{response_text}")
                    logger.info("=" * 60)

                except Exception as e:
                    error_message = f"Failed to communicate with white agent: {str(e)}"
                    logger.error(error_message)
                    break

                # Parse white agent's response
                try:
                    action = parse_white_agent_response(response_text)
                    thought = action.get("thought", "No thought provided")
                    tool = action.get("tool", "finish")
                    params = action.get("params", {})

                    thoughts.append(f"Step {step_count}: {thought}")

                    # Log parsed action details
                    logger.info(f"Parsed action:")
                    logger.info(f"  Thought: {thought}")
                    logger.info(f"  Tool: {tool}")
                    logger.info(f"  Params: {params}")

                    # Save response to file for debugging (optional via env var)
                    if os.getenv("SAVE_DEBUG_RESPONSES", "false").lower() in (
                        "true",
                        "1",
                        "yes",
                    ):
                        debug_response_path = f"{browser_agent.output_dir}/step_{step_count:03d}_response.json"
                        Path(debug_response_path).write_text(
                            json.dumps(action, indent=2)
                        )
                        logger.info(f"Saved response to: {debug_response_path}")

                except Exception as e:
                    error_message = f"Failed to parse white agent response: {str(e)}"
                    logger.error(error_message)
                    break

                # Check if task is finished
                if tool == "finish":
                    logger.info("White agent indicated task completion")
                    success = True
                    break

                # Check if there was a parsing error - provide feedback and retry
                if tool == "error":
                    error_type = params.get("error_type", "unknown")
                    raw_response = params.get("raw_response", "")
                    logger.warning(
                        f"White agent response parsing failed ({error_type}), will retry with feedback"
                    )

                    # Set error feedback for next iteration
                    error_feedback = f"""Your previous response could not be parsed ({error_type}).

Your response was:
{raw_response[:500]}

Please ensure you:
1. Wrap your JSON in <json></json> tags
2. Use valid JSON format with double quotes
3. Include all three required fields: "thought", "tool", and "params"
4. Use one of the valid tools: click, type, select, finish
"""
                    # Don't execute any action, just continue to next step with feedback
                    continue

                # Execute action in browser
                try:
                    logger.info(f"Executing action: {tool} with params {params}")
                    result = await browser_agent.execute_action(tool, **params)

                    if not result.get("success", False):
                        error_message = result.get(
                            "error", "Unknown error during action execution"
                        )
                        logger.warning(f"Action execution failed: {error_message}")
                        # Continue to next step rather than breaking - give agent another chance
                    else:
                        logger.info(f"Action executed successfully")

                except Exception as e:
                    error_message = f"Exception during action execution: {str(e)}"
                    logger.error(error_message)
                    # Continue to next step

            # If we completed all steps without finishing, it's a failure
            if step_count >= max_steps and not success:
                logger.info(f"Reached max steps ({max_steps}) without completion")

            # Save browser session
            final_status = "completed" if success else "failed"
            browser_agent.save_session(
                task_id=task_id,
                task_description=task_description,
                final_response=f"Task {final_status} after {step_count} steps",
                thoughts=thoughts,
            )

            # Create evaluation result
            result = EvalResult(
                winner="white_agent" if success else "none",
                detail={
                    "task_id": task_id,
                    "website": website,
                    "task_description": task_description,
                    "level": level,
                    "success": success,
                    "steps_taken": step_count,
                    "max_steps": max_steps,
                    "thoughts": thoughts,
                    "action_history": browser_agent.get_action_history(),
                    "screenshots": browser_agent.get_screenshots(),
                    "error": error_message,
                },
            )

            # Log evaluation summary
            logger.info("=" * 60)
            logger.info("EVALUATION SUMMARY")
            logger.info("=" * 60)
            logger.info(f"Task: {task_description}")
            logger.info(f"Success: {success}")
            logger.info(f"Steps taken: {step_count}/{max_steps}")
            logger.info(f"Thoughts:")
            for i, thought in enumerate(thoughts, 1):
                logger.info(f"  {i}. {thought}")
            logger.info(f"Action history: {browser_agent.get_action_history()}")
            if error_message:
                logger.info(f"Error: {error_message}")
            logger.info("=" * 60)

            # Add result artifact
            await updater.add_artifact(
                parts=[Part(root=TextPart(text=result.model_dump_json(indent=2)))],
                name="EvaluationResult",
            )

            # Final status update
            await updater.update_status(
                TaskState.working,
                new_agent_text_message(
                    f"Evaluation complete. Success: {success}, Steps taken: {step_count}/{max_steps}"
                ),
            )

        except Exception as e:
            logger.error(f"Unexpected error during evaluation: {str(e)}", exc_info=True)
            error_message = str(e)

            # Try to send error result
            result = EvalResult(
                winner="none",
                detail={
                    "task_id": task_id,
                    "success": False,
                    "error": error_message,
                    "steps_taken": step_count,
                },
            )

            await updater.add_artifact(
                parts=[Part(root=TextPart(text=result.model_dump_json(indent=2)))],
                name="EvaluationResult",
            )

        finally:
            # Clean up
            logger.info("Cleaning up browser and tool provider")
            await browser_agent.stop()
            self._tool_provider.reset()


def browser_judge_agent_card(agent_name: str, card_url: str) -> AgentCard:
    """
    Create the agent card for the Browser Judge.

    Args:
        agent_name: Name of the agent
        card_url: URL where the agent is accessible

    Returns:
        AgentCard describing the agent's capabilities
    """
    skill = AgentSkill(
        id="evaluate_web_agent",
        name="Evaluates web automation agents",
        description="Evaluates a white agent on web browsing tasks using real browser automation.",
        tags=["web", "browser", "evaluation", "playwright", "automation"],
        examples=[
            """{
  "participants": {
    "white_agent": "http://127.0.0.1:9019"
  },
  "config": {
    "task_id": "20a460a8fe1971b84411c5b1e6ac4186",
    "website": "https://www.stubhub.com/",
    "task": "Show theatre events for Las Vegas and select one.",
    "max_steps": 10,
    "level": "easy"
  }
}"""
        ],
    )

    agent_card = AgentCard(
        name=agent_name,
        description="Evaluates web automation agents on browser-based tasks using Playwright.",
        url=card_url,
        version="1.0.0",
        default_input_modes=["text"],
        default_output_modes=["text"],
        capabilities=AgentCapabilities(streaming=True),
        skills=[skill],
    )

    return agent_card


async def main():
    """Main entry point for the Browser Judge agent."""
    parser = argparse.ArgumentParser(
        description="Run the Browser Judge green agent for web automation evaluation."
    )
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host to bind the server to (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=9009,
        help="Port to bind the server to (default: 9009)",
    )
    parser.add_argument(
        "--card-url", type=str, help="External URL for the agent card (optional)"
    )
    parser.add_argument(
        "--cloudflare-quick-tunnel",
        action="store_true",
        help="Use Cloudflare Quick Tunnel for external access",
    )
    args = parser.parse_args()

    # Setup agent URL (with optional cloudflare tunnel)
    if args.cloudflare_quick_tunnel:
        from agentbeats.cloudflare import quick_tunnel

        agent_url_cm = quick_tunnel(f"http://{args.host}:{args.port}")
    else:
        agent_url_cm = contextlib.nullcontext(
            args.card_url or f"http://{args.host}:{args.port}/"
        )

    async with agent_url_cm as agent_url:
        # Create agent and executor
        agent = BrowserJudge()
        executor = GreenExecutor(agent)
        agent_card = browser_judge_agent_card("BrowserJudge", agent_url)

        # Create request handler with task store
        request_handler = DefaultRequestHandler(
            agent_executor=executor,
            task_store=InMemoryTaskStore(),
        )

        # Create A2A server application
        server = A2AStarletteApplication(
            agent_card=agent_card,
            http_handler=request_handler,
        )

        # Configure and start uvicorn server
        logger.info(f"Starting Browser Judge server at {args.host}:{args.port}")
        logger.info(f"Agent card URL: {agent_url}")

        uvicorn_config = uvicorn.Config(
            server.build(), host=args.host, port=args.port, log_level="info"
        )
        uvicorn_server = uvicorn.Server(uvicorn_config)
        await uvicorn_server.serve()


if __name__ == "__main__":
    asyncio.run(main())

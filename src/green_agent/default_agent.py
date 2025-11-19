import json
import logging
from typing import Any, Dict

from green_agent.agent import EvalRequest, GreenAgent
from green_agent.models import Task
from green_agent.task_execution.browser_agent import BrowserAgent
from green_agent.task_loader import TaskLoader
from green_agent.utils.a2a_client import send_message_to_white_agent
from green_agent.utils.response_parser import parse_white_agent_response
from a2a.server.tasks import TaskUpdater

logger = logging.getLogger(__name__)


class DefaultGreenAgent(GreenAgent):
    """Default green agent implementation for web task evaluation."""

    async def run_eval(self, request: EvalRequest, updater: TaskUpdater) -> None:
        """
        Run evaluation of white agent on web tasks.

        Args:
            request: Evaluation request containing white agent URL
            updater: Task updater for sending status updates
        """
        white_agent_url = request.white_agent_url

        task_loader = TaskLoader("data")
        tasks = task_loader.load_all_tasks()
        task = tasks[0]

        browser_agent = BrowserAgent(headless=False, output_dir=".output/test_output")

        try:
            results = await evaluate_task_with_white_agent(
                str(white_agent_url), task, browser_agent, max_steps=10
            )

            logger.info("\n" + "=" * 80)
            logger.info("TEST RESULTS")
            logger.info("=" * 80)
            logger.info(json.dumps(results, indent=2, default=str))

        finally:
            await browser_agent.stop()

    def validate_request(self, request: EvalRequest) -> tuple[bool, str]:
        """Validate evaluation request."""
        return True, "ok"


async def evaluate_task_with_white_agent(
    white_agent_url: str, task: Task, browser_agent: BrowserAgent, max_steps: int = 30
) -> Dict[str, Any]:
    """
    Evaluate a single task using white agent via A2A protocol.

    Args:
        white_agent_url: URL of the white agent to evaluate
        task: Task definition to evaluate
        browser_agent: Browser agent for executing actions
        max_steps: Maximum number of steps to run

    Returns:
        Dictionary with evaluation results and metrics
    """
    logger.info(f"\n{'=' * 60}")
    logger.info("STARTING TASK EVALUATION")
    logger.info(f"{'=' * 60}")
    logger.info(f"Task ID: {task.task_id}")
    logger.info(f"Task: {task.confirmed_task}")
    logger.info(f"Website: {task.website}")
    logger.info(f"Max Steps: {max_steps}")
    logger.info(f"{'=' * 60}\n")

    # Start browser
    await browser_agent.start(str(task.website))

    # Prepare initial message with tools and task description
    initial_message = f"""You are a web automation agent. Your task is:

TASK: {task.confirmed_task}

You are currently on the website: {task.website}

AVAILABLE TOOLS:
1. click - Click on an element
   Parameters: {{"selector": "CSS selector or XPath"}}
   Example: {{"selector": "button#submit"}}

2. type - Type text into an input element
   Parameters: {{"selector": "CSS selector", "text": "text to type"}}
   Example: {{"selector": "input[name='q']", "text": "search query"}}

3. select - Select an option from dropdown
   Parameters: {{"selector": "CSS selector", "value": "option value"}}
   Example: {{"selector": "select#country", "value": "US"}}

4. finish - Complete the task
   Parameters: {{}}
   Use this when you believe the task is complete

RESPONSE FORMAT:
Please respond with your reasoning and the action to take in this format:

<json>
{{
    "thought": "Your reasoning about what to do next",
    "tool": "tool_name",
    "params": {{"param": "value"}}
}}
</json>

CURRENT PAGE STATE:
"""

    context_id = None
    step_count = 0
    success = False
    error_message = None
    thoughts: list[str] = []

    try:
        # Main evaluation loop
        for step in range(max_steps):
            step_count = step + 1

            logger.info(f"\n{'─' * 80}")
            logger.info(f"STEP {step_count}/{max_steps}")
            logger.info(f"{'─' * 80}")

            # Get current page HTML
            html = await browser_agent.get_html()

            # Prepare message
            if step == 0:
                message = initial_message + f"\n\nCURRENT HTML:\n{html[:20000]}"
            else:
                message = f"CURRENT HTML:\n{html[:20000]}\n\n What should we do next?"

            # Send to white agent
            response_text, context_id = await send_message_to_white_agent(
                white_agent_url, message, context_id
            )

            # Parse response
            action = parse_white_agent_response(response_text)

            thought = action.get("thought", "")
            tool = action.get("tool", "finish")
            params = action.get("params", {})
            thoughts.append(thought)
            logger.info(f"\n💭 Thought: {thought}")
            logger.info(f"🔧 Tool: {tool}")
            logger.info(f"⚙️  Params: {params}")

            # Check if finished
            if tool == "finish":
                logger.info(f"\n✓ White agent finished the task!")
                success = True
                break

            # Execute action
            try:
                result = await browser_agent.execute_action(tool, **params)

                if not result["success"]:
                    error_message = result.get("error", "Unknown error")
                    logger.info(f"\n✗ Action failed: {error_message}")
                    # Continue anyway, let white agent know

            except Exception as e:
                error_message = str(e)
                logger.info(f"\n✗ Exception executing action: {e}")
                # Continue anyway

        if step_count >= max_steps:
            logger.info(f"\n⚠️  Reached max steps ({max_steps})")

    except Exception as e:
        error_message = str(e)
        logger.info(f"\n✗ Fatal error: {e}")

    finally:
        # Save session
        final_url = browser_agent.page.url if browser_agent.page else ""
        browser_agent.save_session(
            task_id=task.task_id,
            task_description=task.confirmed_task,
            final_response=f"Completed {step_count} steps. Success: {success}. Final URL: {final_url}",
            thoughts=thoughts,
        )

    # Prepare results
    results = {
        "task_id": task.task_id,
        "task": task.confirmed_task,
        "success": success,
        "steps_taken": step_count,
        "reference_length": task.reference_length,
        "action_history": browser_agent.get_action_history(),
        "screenshots": browser_agent.get_screenshots(),
        "error": error_message,
        "final_url": browser_agent.page.url if browser_agent.page else "",
    }

    return results

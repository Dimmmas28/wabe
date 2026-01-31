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
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import uvicorn

# A2A framework
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore, TaskUpdater
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentSkill,
    FilePart,
    FileWithBytes,
    Part,
    TaskState,
    TextPart,
)
from a2a.utils import new_agent_text_message
from dotenv import load_dotenv

# AgentBeats framework
from agentbeats.green_executor import GreenAgent, GreenExecutor
from agentbeats.models import EvalRequest, EvalResult
from agentbeats.tool_provider import ToolProvider

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Existing WABE components
from eval.benchmark import Config, run_benchmark_eval
from green_agent.constants import (
    EVAL_MODE,
    EVAL_MODEL,
    EVAL_RESULT_OUTPUT_DIR,
    MAX_HTML_CONTEXT_LENGTH,
    MAX_PARALLEL_TASKS,
    TASK_RESULT_OUTPUT_DIR,
)

# Default score threshold for evaluation (matches benchmark.py default)
EVAL_SCORE_THRESHOLD = 3

# Maximum consecutive parse errors before giving up on a task
# Prevents wasting all steps on a model that won't follow format instructions
MAX_CONSECUTIVE_PARSE_ERRORS = 3
from green_agent.prompts import (
    BrowserJudgePrompts,
    build_tools_prompt,
)
from shared.browser_agent import BrowserAgent
from shared.response_parser import parse_white_agent_response

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@dataclass
class TaskResult:
    """Result of a single task execution."""

    task_id: str
    task_id_with_timestamp: str
    website: str
    task_description: str
    level: str
    success: bool
    step_count: int
    max_steps: int
    thoughts: list[str]
    action_history: list[str]
    screenshots: list[str]
    error_message: str | None


class BrowserJudge(GreenAgent):
    """
    Green agent that evaluates white agents on web browsing tasks.

    This agent:
    1. Receives an evaluation request with white agent URL and task configs
    2. Runs multiple tasks in parallel, each with isolated browser and tool provider
    3. Returns aggregated evaluation results
    """

    def __init__(self, limit: int | None = None, level: str | None = None):
        """Initialize the Browser Judge agent.

        Args:
            limit: Maximum number of tasks to run (None = all tasks)
            level: Filter tasks by difficulty level ("easy", "medium", "hard", or None for all)
        """
        self._required_roles = ["white_agent"]
        self._required_task_keys = ["task_id", "website", "task"]
        self._limit = limit
        self._level = level
        logger.info(f"BrowserJudge initialized (limit={limit}, level={level})")

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

        # Get tasks list - check request.tasks, then config.tasks, then fallback to config as single task
        if request.tasks:
            tasks = request.tasks
        elif "tasks" in request.config:
            tasks = request.config["tasks"]
        else:
            tasks = [request.config]

        # Validate each task has required keys
        for i, task in enumerate(tasks):
            # Merge base config with task-specific config
            merged_task = {**request.config, **task}
            missing_keys = set(self._required_task_keys) - set(merged_task.keys())
            if missing_keys:
                return False, f"Task {i} missing required keys: {missing_keys}"

        logger.info(f"Request validation passed: {len(tasks)} task(s)")
        return True, "ok"

    async def run_eval(self, req: EvalRequest, updater: TaskUpdater) -> None:
        """
        Run the browser task evaluation for multiple tasks in parallel.

        Args:
            req: The evaluation request containing participants and config
            updater: TaskUpdater for sending status updates and artifacts
        """
        logger.info(f"Starting browser evaluation: {req}")

        # Get tasks list - check request.tasks, then config.tasks, then fallback to config as single task
        if req.tasks:
            tasks_config = req.tasks
        elif "tasks" in req.config:
            tasks_config = req.config["tasks"]
        else:
            tasks_config = [req.config]

        # Merge base config with each task config
        merged_tasks = [{**req.config, **task} for task in tasks_config]

        # Apply filtering based on level and limit
        if self._level:
            original_count = len(merged_tasks)
            merged_tasks = [
                task for task in merged_tasks if task.get("level") == self._level
            ]
            logger.info(
                f"Filtered tasks by level '{self._level}': {original_count} -> {len(merged_tasks)} task(s)"
            )

        if self._limit and self._limit > 0:
            original_count = len(merged_tasks)
            merged_tasks = merged_tasks[: self._limit]
            logger.info(
                f"Limited tasks to {self._limit}: {original_count} -> {len(merged_tasks)} task(s)"
            )

        await updater.update_status(
            TaskState.working,
            new_agent_text_message(
                f"Starting evaluation for {len(merged_tasks)} task(s)"
            ),
        )

        # Run all tasks in parallel with concurrency limit
        logger.info(
            f"Running {len(merged_tasks)} tasks in parallel (max {MAX_PARALLEL_TASKS} concurrent)"
        )
        semaphore = asyncio.Semaphore(MAX_PARALLEL_TASKS)

        async def run_with_semaphore(task_config: dict, task_idx: int):
            async with semaphore:
                return await self._run_single_task(task_config, req, updater, task_idx)

        results = await asyncio.gather(
            *[
                run_with_semaphore(task_config, task_idx)
                for task_idx, task_config in enumerate(merged_tasks)
            ],
            return_exceptions=True,
        )

        # Process results
        task_results: list[TaskResult] = []
        for i, result in enumerate(results):
            if isinstance(result, BaseException):
                logger.error(f"Task {i} failed with exception: {result}")
                # Create error result
                task_config = merged_tasks[i]
                task_results.append(
                    TaskResult(
                        task_id=task_config.get("task_id", f"task_{i}"),
                        task_id_with_timestamp=f"{task_config.get('task_id', f'task_{i}')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                        website=task_config.get("website", ""),
                        task_description=task_config.get("task", ""),
                        level=task_config.get("level", "unknown"),
                        success=False,
                        step_count=0,
                        max_steps=int(task_config.get("max_steps", 10)),
                        thoughts=[],
                        action_history=[],
                        screenshots=[],
                        error_message=str(result),
                    )
                )
            elif isinstance(result, TaskResult):
                task_results.append(result)

        # Run benchmark evaluation once after all tasks complete
        success_rate = self._run_final_evaluation()

        # Parse LLM evaluation results to get per-task success
        llm_predicted_labels = self._parse_eval_results()

        # Create aggregated result using LLM evaluation for consistency
        total_tasks = len(task_results)

        # Build task details with LLM-evaluated success
        task_details = []
        for r in task_results:
            # Use LLM predicted_label if available, otherwise fall back to browser loop success
            llm_success = llm_predicted_labels.get(r.task_id_with_timestamp)
            if llm_success is not None:
                task_success = bool(llm_success)
            else:
                # Fallback: if LLM didn't evaluate this task, use browser loop result
                logger.warning(
                    f"No LLM evaluation found for task {r.task_id_with_timestamp}, "
                    f"using browser loop result: {r.success}"
                )
                task_success = r.success

            task_details.append(
                {
                    "task_id": r.task_id,
                    "task_id_with_timestamp": r.task_id_with_timestamp,
                    "website": r.website,
                    "task_description": r.task_description,
                    "level": r.level,
                    "success": task_success,
                    "steps_taken": r.step_count,
                    "max_steps": r.max_steps,
                    "thoughts": r.thoughts,
                    "action_history": r.action_history,
                    "screenshots": r.screenshots,
                    "error": r.error_message,
                }
            )

        # Calculate successful_tasks from LLM-evaluated success for consistency
        successful_tasks = sum(1 for t in task_details if t["success"])

        aggregated_result = EvalResult(
            winner="white_agent" if successful_tasks > 0 else "none",
            detail={
                "success_rate": success_rate,
                "successful_tasks": successful_tasks,
                "total_tasks": total_tasks,
                "tasks": task_details,
            },
        )

        await updater.add_artifact(
            parts=[
                Part(root=TextPart(text=aggregated_result.model_dump_json(indent=2)))
            ],
            name="EvaluationResult",
        )
        await updater.update_status(
            TaskState.working,
            new_agent_text_message(
                f"Evaluation complete. {successful_tasks}/{total_tasks} tasks successful. Success rate: {success_rate}"
            ),
        )

    def _run_final_evaluation(self) -> float:
        """Run benchmark evaluation once after all tasks complete."""
        # Clean up incomplete result directories before evaluation
        results_dir = Path(TASK_RESULT_OUTPUT_DIR)
        if results_dir.exists():
            for task_dir in results_dir.iterdir():
                if task_dir.is_dir():
                    result_file = task_dir / "result.json"
                    if not result_file.exists():
                        logger.warning(
                            f"Removing incomplete result directory: {task_dir.name}"
                        )
                        shutil.rmtree(task_dir)

        success_rate = run_benchmark_eval(
            Config(
                api_key=os.getenv("GOOGLE_API_KEY", ""),
                mode=EVAL_MODE,
                trajectories_dir=str(Path(TASK_RESULT_OUTPUT_DIR)),
                model=EVAL_MODEL,
                output_path=EVAL_RESULT_OUTPUT_DIR,
            )
        )
        return success_rate

    def _parse_eval_results(self) -> dict[str, int]:
        """
        Parse LLM evaluation results from the JSONL file.

        Returns:
            Dictionary mapping task_id_with_timestamp to predicted_label (0 or 1)
        """
        eval_file = Path(EVAL_RESULT_OUTPUT_DIR) / (
            f"{EVAL_MODE}_{EVAL_MODEL}_score_threshold_{EVAL_SCORE_THRESHOLD}_auto_eval_results.json"
        )

        predicted_labels: dict[str, int] = {}

        if not eval_file.exists():
            logger.warning(f"Evaluation results file not found: {eval_file}")
            return predicted_labels

        try:
            with open(eval_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        result = json.loads(line)
                        task_id = result.get("task_id", "")
                        label = result.get("predicted_label", 0)
                        predicted_labels[task_id] = label
                    except json.JSONDecodeError as e:
                        logger.warning(f"Failed to parse eval result line: {e}")
                        continue
        except Exception as e:
            logger.error(f"Failed to read evaluation results: {e}")

        logger.info(f"Parsed {len(predicted_labels)} LLM evaluation results")
        return predicted_labels

    async def _run_single_task(
        self,
        task_config: dict[str, Any],
        req: EvalRequest,
        updater: TaskUpdater,
        task_idx: int,
    ) -> TaskResult:
        """
        Run a single task with isolated browser and tool provider.

        Args:
            task_config: Configuration for this specific task
            req: The original evaluation request (for participants)
            updater: TaskUpdater for status updates
            task_idx: Index of this task (for logging)

        Returns:
            TaskResult with the outcome of this task
        """
        # Extract task configuration
        task_id = task_config["task_id"]
        website = task_config["website"]
        task_description = task_config["task"]
        max_steps = int(task_config.get("max_steps", 10))
        step_delay = float(task_config.get("step_delay", 2.0))
        level = task_config.get("level", "unknown")

        # Generate timestamp for unique directory
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        task_id_with_timestamp = f"{task_id}_{timestamp}"

        logger.info(f"[Task {task_idx}] Starting task: {task_id}")

        await updater.update_status(
            TaskState.working,
            new_agent_text_message(f"[Task {task_idx}] Starting: {task_id}"),
        )

        # Create isolated resources for this task
        tool_provider = ToolProvider()
        browser_agent = BrowserAgent(
            output_dir=f"{TASK_RESULT_OUTPUT_DIR}/{task_id_with_timestamp}",
        )

        step_count = 0
        success = False
        thoughts: list[str] = []
        error_message: str | None = None

        try:
            logger.info(f"[Task {task_idx}] Starting browser at {website}")
            await browser_agent.start(website)

            success, step_count, thoughts, error_message = await self._run_task_loop(
                max_steps=max_steps,
                step_delay=step_delay,
                browser_agent=browser_agent,
                tool_provider=tool_provider,
                updater=updater,
                task_description=task_description,
                website=website,
                white_agent_url=str(req.participants["white_agent"]),
                task_idx=task_idx,
            )

            # Save browser session
            final_status = "completed" if success else "failed"
            browser_agent.save_session(
                task_id=task_id_with_timestamp,
                task_description=task_description,
                final_response=f"Task {final_status} after {step_count} steps",
                thoughts=thoughts,
            )

            self._log_evaluation_summary(
                task_description,
                step_count,
                max_steps,
                success,
                thoughts,
                browser_agent.get_action_history(),
                error_message,
                task_idx,
            )

        except Exception as e:
            logger.error(f"[Task {task_idx}] Unexpected error: {str(e)}", exc_info=True)
            error_message = str(e)
            success = False

        finally:
            logger.info(f"[Task {task_idx}] Cleaning up browser")
            await browser_agent.stop()

        return TaskResult(
            task_id=task_id,
            task_id_with_timestamp=task_id_with_timestamp,
            website=website,
            task_description=task_description,
            level=level,
            success=success,
            step_count=step_count,
            max_steps=max_steps,
            thoughts=thoughts,
            action_history=browser_agent.get_action_history(),
            screenshots=browser_agent.get_screenshots(),
            error_message=error_message,
        )

    async def _run_task_loop(
        self,
        max_steps: int,
        step_delay: float,
        browser_agent: BrowserAgent,
        tool_provider: ToolProvider,
        updater: TaskUpdater,
        task_description: str,
        website: str,
        white_agent_url: str,
        task_idx: int,
    ):
        """Run the main task execution loop."""
        step_count: int = 0
        success = False
        thoughts: list[str] = []
        error_message: str | None = None
        browser_closed = False

        # Get dynamic tools from MCP client
        tools = await browser_agent.get_tools()
        logger.info(f"[Task {task_idx}] Retrieved {len(tools)} tools from MCP client")

        # Log tool details for debugging
        logger.info("=" * 60)
        logger.info(f"[Task {task_idx}] AVAILABLE TOOLS FOR WHITE AGENT:")
        logger.info("=" * 60)
        for tool in tools:
            tool_name = tool.get("name", "unknown")
            tool_desc = tool.get("description", "No description")
            schema = tool.get("inputSchema", {})
            required_params = schema.get("required", [])
            properties = schema.get("properties", {})

            logger.info(f"\n{tool_name}:")
            logger.info(f"  Description: {tool_desc}")
            if properties:
                logger.info("  Parameters:")
                for param_name, param_schema in properties.items():
                    param_type = param_schema.get("type", "any")
                    param_desc = param_schema.get("description", "")
                    req_marker = (
                        " (required)"
                        if param_name in required_params
                        else " (optional)"
                    )
                    logger.info(f"    - {param_name}: {param_type}{req_marker}")
                    if param_desc:
                        logger.info(f"      {param_desc}")
        logger.info("=" * 60)

        # Prepare initial prompt for white agent
        initial_prompt = BrowserJudgePrompts.task_run_prompt(
            task_description, website, tools
        )

        error_feedback = None
        consecutive_parse_errors = 0

        # Exponential backoff for step delay
        # Start with configured delay, increase on rate limit errors, decrease on success
        current_delay = step_delay
        min_delay = step_delay  # Don't go below configured minimum
        max_delay = step_delay * 8  # Cap at 8x the base delay
        consecutive_successes = 0

        for step in range(max_steps):
            step_count = step + 1
            logger.info(f"[Task {task_idx}] Starting step {step_count}/{max_steps}")

            # Add delay between steps to avoid rate limiting (except first step)
            if step > 0 and current_delay > 0:
                logger.info(
                    f"[Task {task_idx}] Waiting {current_delay:.1f}s before next step..."
                )
                await asyncio.sleep(current_delay)

            await updater.update_status(
                TaskState.working,
                new_agent_text_message(
                    f"[Task {task_idx}] Step {step_count}/{max_steps}"
                ),
            )

            # Get current page accessibility snapshot via MCP
            snapshot = await browser_agent.get_snapshot()

            # Truncate snapshot if too long
            snapshot_truncated = snapshot[:MAX_HTML_CONTEXT_LENGTH]
            if len(snapshot) > MAX_HTML_CONTEXT_LENGTH:
                snapshot_truncated += "\n\n[Snapshot truncated for length...]"

            # Prepare multi-part message
            parts = []

            if step == 0:
                text_content = (
                    initial_prompt + f"\n\nCURRENT PAGE SNAPSHOT:\n{snapshot_truncated}"
                )
            else:
                tools_section = build_tools_prompt(tools)

                if error_feedback:
                    text_content = f"""ERROR IN PREVIOUS RESPONSE:
{error_feedback}

Please try again with the correct format. Remember to wrap your JSON in <json></json> tags.

{tools_section}

CURRENT PAGE SNAPSHOT:
{snapshot_truncated}

What should we do next?"""
                    error_feedback = None
                else:
                    text_content = f"""{tools_section}

CURRENT PAGE SNAPSHOT:
{snapshot_truncated}

What should we do next?"""

            parts.append(Part(root=TextPart(text=text_content)))

            logger.info(
                f"[Task {task_idx}] Text content being sent (first 300 chars):\n{text_content[:300]}"
            )

            # Add screenshot
            screenshot_data = browser_agent.get_latest_screenshot_base64()
            if screenshot_data:
                base64_string, screenshot_path = screenshot_data
                file_part = FilePart(
                    file=FileWithBytes(
                        bytes=base64_string,
                        mime_type="image/jpeg",
                        name=Path(screenshot_path).name,
                    )
                )
                parts.append(Part(root=file_part))
            else:
                logger.warning(f"[Task {task_idx}] No screenshot available")

            logger.info("=" * 60)
            logger.info(
                f"[Task {task_idx}] STEP {step_count}/{max_steps}: Sending to white agent"
            )
            logger.info("=" * 60)

            # Save snapshot for debugging
            if os.getenv("SAVE_DEBUG_HTML", "false").lower() in ("true", "1", "yes"):
                debug_snapshot_path = (
                    f"{browser_agent.output_dir}/step_{step_count:03d}_snapshot.txt"
                )
                Path(debug_snapshot_path).write_text(snapshot)

            # Send to white agent
            # Continue same conversation - white agent controls its own history strategy
            # (e.g., include_contents='none' for stateless, or 'default' for full history)
            # Add timeout to prevent jobs from hanging indefinitely in CI
            WHITE_AGENT_TIMEOUT = 300  # 5 minutes max per step
            try:
                response_text = await asyncio.wait_for(
                    tool_provider.talk_to_agent(
                        url=white_agent_url,
                        new_conversation=(step == 0),
                        parts=parts,
                    ),
                    timeout=WHITE_AGENT_TIMEOUT,
                )

                logger.info("=" * 60)
                logger.info(
                    f"[Task {task_idx}] STEP {step_count}: Response from white agent"
                )
                logger.info("=" * 60)
                logger.info(f"Full response:\n{response_text}")
                logger.info("=" * 60)

                # Success - gradually decrease delay (but not below minimum)
                consecutive_successes += 1
                if consecutive_successes >= 3 and current_delay > min_delay:
                    current_delay = max(min_delay, current_delay * 0.8)
                    logger.info(
                        f"[Task {task_idx}] Decreased step delay to {current_delay:.1f}s after {consecutive_successes} successes"
                    )

            except asyncio.TimeoutError:
                error_message = (
                    f"White agent response timed out after {WHITE_AGENT_TIMEOUT}s"
                )
                logger.error(f"[Task {task_idx}] {error_message}")
                # Don't retry on timeout - likely indicates a hung LLM call
                break

            except Exception as e:
                error_str = str(e).lower()
                is_rate_limit = (
                    "429" in error_str
                    or "resource_exhausted" in error_str
                    or "too many requests" in error_str
                )
                is_timeout = "timeout" in error_str or isinstance(e, TimeoutError)

                if is_timeout:
                    error_message = f"White agent timed out: {str(e)}"
                    logger.error(f"[Task {task_idx}] {error_message}")
                    break

                if is_rate_limit:
                    # Rate limit hit - increase delay exponentially
                    consecutive_successes = 0
                    old_delay = current_delay
                    current_delay = min(max_delay, current_delay * 2)
                    logger.warning(
                        f"[Task {task_idx}] Rate limit hit, increasing step delay from {old_delay:.1f}s to {current_delay:.1f}s"
                    )
                    # Wait extra time before retry
                    await asyncio.sleep(current_delay)
                    continue  # Retry this step

                error_message = f"Failed to communicate with white agent: {str(e)}"
                logger.error(f"[Task {task_idx}] {error_message}")
                break

            # Parse response
            try:
                action = parse_white_agent_response(response_text)
                thought = action.get("thought", "No thought provided")
                tool = action.get("tool", "finish")
                params = action.get("params", {})

                thoughts.append(f"Step {step_count}: {thought}")

                logger.info(f"[Task {task_idx}] Parsed action:")
                logger.info(f"  Thought: {thought}")
                logger.info(f"  Tool: {tool}")
                logger.info(f"  Params: {params}")

                if os.getenv("SAVE_DEBUG_RESPONSES", "false").lower() in (
                    "true",
                    "1",
                    "yes",
                ):
                    debug_response_path = f"{browser_agent.output_dir}/step_{step_count:03d}_response.json"
                    Path(debug_response_path).write_text(json.dumps(action, indent=2))

            except Exception as e:
                error_message = f"Failed to parse white agent response: {str(e)}"
                logger.error(f"[Task {task_idx}] {error_message}")
                break

            # Check if finished
            if tool == "finish":
                logger.info(f"[Task {task_idx}] Task completed")
                success = True
                break

            # Handle parsing error
            if tool == "error":
                error_type = params.get("error_type", "unknown")
                consecutive_parse_errors += 1
                logger.warning(
                    f"[Task {task_idx}] Parse error ({error_type}), attempt {consecutive_parse_errors}/{MAX_CONSECUTIVE_PARSE_ERRORS}"
                )

                # After too many consecutive parse errors, give up on this task
                if consecutive_parse_errors >= MAX_CONSECUTIVE_PARSE_ERRORS:
                    logger.error(
                        f"[Task {task_idx}] Too many consecutive parse errors ({consecutive_parse_errors}), "
                        f"marking task as failed and moving on"
                    )
                    error_message = f"Task failed after {consecutive_parse_errors} consecutive parse errors"
                    break

                error_feedback = f"Your previous response could not be parsed ({error_type}). Try again."
                continue
            else:
                # Reset counter on successful parse
                consecutive_parse_errors = 0

            # Execute action
            try:
                logger.info(f"[Task {task_idx}] Executing: {tool} with params {params}")
                result = await browser_agent.execute_action(tool, **params)

                if result.get("browser_closed", False):
                    browser_closed = True
                    logger.warning(f"[Task {task_idx}] Browser close detected")

                    if len(browser_agent.action_history) > 0:
                        success = True
                        logger.warning(
                            f"[Task {task_idx}] Setting success=True after {len(browser_agent.action_history)} actions"
                        )
                    break

                if not result.get("success", False):
                    action_error = result.get("error", "Unknown error")
                    logger.warning(f"[Task {task_idx}] Action failed: {action_error}")

                    error_feedback = f"""Your previous action failed with error:
{action_error}

Tool: {tool}
Parameters you provided: {params}

Please check the AVAILABLE TOOLS section for the correct required parameters.
Most interactive tools require BOTH:
  - "element": Human-readable description (e.g., "Search textbox")
  - "ref": Snapshot reference (e.g., "s8")

Try again with the correct parameters."""
                else:
                    logger.info(f"[Task {task_idx}] Action executed successfully")

            except Exception as e:
                error_message = f"Exception during action execution: {str(e)}"
                logger.error(f"[Task {task_idx}] {error_message}")
                if "closed" in str(e).lower() or "disconnected" in str(e).lower():
                    browser_closed = True
                    if len(browser_agent.action_history) > 0:
                        success = True
                    break

        if step_count >= max_steps and not success:
            logger.info(f"[Task {task_idx}] Reached max steps without completion")

        if browser_closed:
            logger.info(f"[Task {task_idx}] Terminated due to browser close")

        return success, step_count, thoughts, error_message

    def _log_evaluation_summary(
        self,
        task_description: str,
        step_count: int,
        max_steps: int,
        success: bool,
        thoughts: list[str],
        action_history: list[str],
        error_message: str | None,
        task_idx: int = 0,
    ):
        logger.info("=" * 60)
        logger.info(f"[Task {task_idx}] EVALUATION SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Task: {task_description}")
        logger.info(f"Success: {success}")
        logger.info(f"Steps taken: {step_count}/{max_steps}")
        logger.info("Thoughts:")
        for i, thought in enumerate(thoughts, 1):
            logger.info(f"  {i}. {thought}")
        logger.info(f"Action history: {action_history}")
        if error_message:
            logger.info(f"Error: {error_message}")
        logger.info("=" * 60)


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
    "max_steps": 10
  },
  "tasks": [
    {
      "task_id": "task_1",
      "website": "https://www.stubhub.com/",
      "task": "Show theatre events for Las Vegas and select one.",
      "level": "easy"
    },
    {
      "task_id": "task_2",
      "website": "https://www.example.com/",
      "task": "Find contact information.",
      "level": "easy"
    }
  ]
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
    parser.add_argument(
        "--limit",
        type=int,
        default=os.environ.get("TASK_LIMIT"),
        help="Maximum number of tasks to run (default: all tasks, can set via TASK_LIMIT env var)",
    )
    parser.add_argument(
        "--level",
        type=str,
        choices=["easy", "medium", "hard"],
        default=os.environ.get("TASK_LEVEL"),
        help="Filter tasks by difficulty level (easy, medium, or hard, can set via TASK_LEVEL env var)",
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
        # Create agent and executor with filtering parameters
        agent = BrowserJudge(limit=args.limit, level=args.level)
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

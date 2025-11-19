import asyncio
import json
import logging
from utils import my_a2a
from utils.common_utils import build_url
from pathlib import Path
from datetime import datetime
from a2a.types import SendMessageSuccessResponse, Task

logger = logging.getLogger(__name__)


def init_file_logging(suffix: str = "app"):
    logs_dir = Path(".logs")
    logs_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_filename = logs_dir / f"{timestamp}_{suffix}.log"

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Remove existing handlers to avoid duplicates
    root_logger.handlers.clear()

    # Create file handler
    file_handler = logging.FileHandler(log_filename, encoding="utf-8")
    file_handler.setLevel(logging.INFO)

    # Create formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    file_handler.setFormatter(formatter)

    # Add handler to logger
    root_logger.addHandler(file_handler)


async def launch_evaluation():
    init_file_logging()

    green_address = ("localhost", 9001)
    green_url = build_url(*green_address)

    white_address = ("localhost", 9002)
    white_url = build_url(*white_address)

    # send the task description
    logger.info("Sending task description to green agent...")
    task = {"white_agent_url": white_url}
    task_text = f"""
        {json.dumps(task, indent=2)}
    """
    logger.info("Task description:")
    logger.info(task_text)
    logger.info("Sending...")
    response = await my_a2a.send_message(green_url, task_text, context_id="b1")
    logger.info("Response from green agent:")
    # logger.info(response)
    if isinstance(response.root, SendMessageSuccessResponse):
        if isinstance(response.root.result, Task):
            task_id = response.root.result.id

    # while True:
    #     response = await my_a2a.send_task(
    #         green_url, task_text, task_id=task_id, context_id="b1"
    #     )
    #     logger.info("Response from green agent:")
    #     logger.info(response)

    #     status = response.root.result.status.state

    #     print(f"Status: {status}")

    #     if status in ["completed", "failed", "canceled"]:
    #         print(f"Final result: {response.root.result}")
    #         break

    #     await asyncio.sleep(2)

    logger.info("Evaluation complete.")


def main():
    """Entry point for the dev script."""
    import asyncio

    asyncio.run(launch_evaluation())


if __name__ == "__main__":
    main()

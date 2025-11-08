import json
import logging
from utils import my_a2a
from utils.common_utils import build_url
from utils.my_a2a import wait_agent_ready
from white_agent.a2a import start_white_agent
import multiprocessing
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


def init_file_logging():
    logs_dir = Path(".logs")
    logs_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_filename = logs_dir / f"app_{timestamp}.log"

    logging.basicConfig(
        filename=log_filename,
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


async def launch_evaluation():
    init_file_logging()

    green_address = ("localhost", 9001)
    green_url = build_url(*green_address)
    p_green = multiprocessing.Process(target=start_white_agent, args=green_address)
    p_green.start()
    assert await wait_agent_ready(green_url), "Green agent not ready in time"
    logger.info("Green agent is ready.")

    white_address = ("localhost", 9002)
    white_url = build_url(*white_address)
    p_white = multiprocessing.Process(target=start_white_agent, args=white_address)
    p_white.start()
    assert await wait_agent_ready(white_url), "White agent not ready in time"
    logger.info("White agent is ready.")

    # send the task description
    logger.info("Sending task description to green agent...")
    task = {"white_agent_url": white_url}
    task_text = f"""
        {json.dumps(task, indent=2)}
    """
    logger.info("Task description:")
    logger.info(task_text)
    logger.info("Sending...")
    response = await my_a2a.send_message(green_url, task_text)
    logger.info("Response from green agent:")
    logger.info(response)

    logger.info("Evaluation complete. Terminating agents...")
    p_green.terminate()
    p_green.join()
    p_white.terminate()
    p_white.join()
    logger.info("Agents terminated.")


if __name__ == "__main__":
    import asyncio

    asyncio.run(launch_evaluation())

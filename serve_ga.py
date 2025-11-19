import logging
from green_agent.a2a.server import start_green_agent
from main import init_file_logging


def launch_evaluation():
    init_file_logging("green")

    logger = logging.getLogger(__name__)

    green_address = ("localhost", 9001)
    start_green_agent(*green_address)
    logger.info("Green agent is ready.")


if __name__ == "__main__":
    launch_evaluation()

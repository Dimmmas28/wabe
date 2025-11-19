import logging
from main import init_file_logging
from white_agent.a2a import start_white_agent

logger = logging.getLogger(__name__)


def launch_white_agent():
    init_file_logging("white")

    white_address = ("localhost", 9002)
    start_white_agent(*white_address)
    logger.info("White agent is ready.")


if __name__ == "__main__":
    launch_white_agent()

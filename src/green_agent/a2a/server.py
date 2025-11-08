import logging
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
import uvicorn

from green_agent.a2a.agent_card import prepare_agent_card
from green_agent.a2a.agent_executor import GreenExecutor
from green_agent.default_agent import DefaultGreenAgent
from utils.common_utils import build_url

logger = logging.getLogger(__name__)


def start_green_agent(host: str, port: int):
    logger.info("Starting green agent...")

    agent = DefaultGreenAgent()
    request_handler = DefaultRequestHandler(
        agent_executor=GreenExecutor(agent),
        task_store=InMemoryTaskStore(),
    )

    url = build_url(host, port)
    app = A2AStarletteApplication(
        agent_card=prepare_agent_card(url),
        http_handler=request_handler,
    )

    uvicorn.run(app.build(), host=host, port=port)

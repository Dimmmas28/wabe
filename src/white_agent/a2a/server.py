import logging
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
import uvicorn

from utils.common_utils import build_url
from white_agent.a2a.agent_card import prepare_agent_card
from white_agent.a2a.agent_executor import WhiteAgentExecutor
from white_agent.default_agent import DefaultWhiteAgent

logger = logging.getLogger(__name__)


def start_white_agent(host: str, port: int, secure: bool = False):
    logger.info("Starting white agent...")

    agent = DefaultWhiteAgent()
    request_handler = DefaultRequestHandler(
        agent_executor=WhiteAgentExecutor(agent),
        task_store=InMemoryTaskStore(),
    )

    url = build_url(host, port, secure)
    server = A2AStarletteApplication(
        agent_card=prepare_agent_card(url),
        http_handler=request_handler,
    )

    uvicorn.run(server.build(), host=host, port=port)

import logging
from green_agent.agent import EvalRequest, GreenAgent
from utils import my_a2a
from a2a.types import SendMessageSuccessResponse, Message
from a2a.utils import get_text_parts

logger = logging.getLogger(__name__)


class DefaultGreenAgent(GreenAgent):
    async def run_eval(self, request: EvalRequest) -> None:
        white_agent_url = request.white_agent_url

        task_description = """
            Read all new messages . Return list str.
        """

        next_green_message = task_description

        logger.info(
            f"@@@ Green agent: Sending message to white agent... -->\n{next_green_message}"
        )
        white_agent_response = await my_a2a.send_message(
            str(white_agent_url), next_green_message
        )
        res_root = white_agent_response.root
        assert isinstance(res_root, SendMessageSuccessResponse)
        res_result = res_root.result
        assert isinstance(
            res_result, Message
        )  # though, a robust design should also support Task

        text_parts = get_text_parts(res_result.parts)
        assert len(text_parts) == 1, (
            "Expecting exactly one text part from the white agent"
        )
        white_text = text_parts[0]
        print(f"@@@ White agent response:\n{white_text}")

    def validate_request(self, request: EvalRequest) -> tuple[bool, str]:
        return True, "ok"

import logging
import httpx
import asyncio
import uuid


from a2a.client import A2ACardResolver, A2AClient
from a2a.types import (
    AgentCard,
    Part,
    TextPart,
    MessageSendParams,
    Message,
    Role,
    SendMessageRequest,
    SendMessageResponse,
)

logger = logging.getLogger(__name__)


async def get_agent_card(
    url: str, httpx_client: httpx.AsyncClient | None = None
) -> AgentCard | None:
    if httpx_client:
        return await _get_card(url, httpx_client)

    async with httpx.AsyncClient() as httpx_client:
        return await _get_card(url, httpx_client)


async def _get_card(url: str, httpx_client: httpx.AsyncClient) -> AgentCard | None:
    resolver = A2ACardResolver(httpx_client=httpx_client, base_url=url)
    return await resolver.get_agent_card()


async def wait_agent_ready(url: str, timeout_cnt: int = 3):
    retry_cnt = 0

    while retry_cnt < timeout_cnt:
        retry_cnt += 1
        try:
            card = await get_agent_card(url)
            if card is None:
                logger.info(
                    f"Agent card not available yet..., retrying {retry_cnt}/{timeout_cnt}"
                )
            else:
                return True

        except Exception:
            pass
        await asyncio.sleep(1)

    return False


async def send_message(
    url: str, message: str, task_id: str | None = None, context_id: str | None = None
) -> SendMessageResponse:
    async with httpx.AsyncClient() as httpx_client:
        card = await get_agent_card(url, httpx_client)
        client = A2AClient(httpx_client=httpx_client, agent_card=card)

        message_id = uuid.uuid4().hex
        params = MessageSendParams(
            message=Message(
                role=Role.user,
                parts=[Part(TextPart(text=message))],
                message_id=message_id,
                task_id=task_id,
                context_id=context_id,
            )
        )
        request_id = uuid.uuid4().hex
        request = SendMessageRequest(id=request_id, params=params)
        response = await client.send_message(request)
        return response

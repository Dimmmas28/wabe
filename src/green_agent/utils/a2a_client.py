"""A2A client utilities for communicating with white agents."""

import logging
from typing import Optional

from a2a.types import Message, SendMessageSuccessResponse
from a2a.utils import get_text_parts
from utils import my_a2a

logger = logging.getLogger(__name__)


async def send_message_to_white_agent(
    white_agent_url: str, message_text: str, context_id: Optional[str] = None
) -> tuple[str, str]:
    """
    Send message to white agent via A2A protocol.

    Args:
        white_agent_url: URL of the white agent to send message to
        message_text: Message content to send
        context_id: Optional context ID for continuing a conversation

    Returns:
        Tuple of (response_text, context_id)

    Raises:
        AssertionError: If response format is invalid
    """

    logger.info(f"\n{'=' * 60}")
    logger.info("→ GREEN AGENT: Sending to white agent...")
    logger.info(f"{'=' * 60}")
    logger.info(message_text)
    # logger.info(message_text[:500] + "..." if len(message_text) > 500 else message_text)

    response = await my_a2a.send_message(
        white_agent_url, message_text, context_id=context_id
    )

    res_root = response.root
    assert isinstance(res_root, SendMessageSuccessResponse)

    res_result = res_root.result
    assert isinstance(res_result, Message)

    if context_id is None:
        context_id = res_result.context_id

    text_parts = get_text_parts(res_result.parts)
    assert len(text_parts) >= 1, "Expecting at least one text part from white agent"

    response_text = text_parts[0]

    logger.info(f"\n{'=' * 60}")
    logger.info("← WHITE AGENT: Response received")
    logger.info(f"{'=' * 60}")
    logger.info(
        response_text[:500] + "..." if len(response_text) > 500 else response_text
    )

    return response_text, context_id

import asyncio
import logging
from uuid import uuid4

import httpx
from a2a.client import A2ACardResolver, ClientConfig, ClientFactory, Consumer
from a2a.types import DataPart, Message, Part, Role, TextPart

DEFAULT_TIMEOUT = 300
logger = logging.getLogger(__name__)


def create_message(
    *, role: Role = Role.user, text: str, context_id: str | None = None
) -> Message:
    return Message(
        kind="message",
        role=role,
        parts=[Part(TextPart(kind="text", text=text))],
        message_id=uuid4().hex,
        context_id=context_id,
    )


def merge_parts(parts: list[Part]) -> str:
    chunks = []
    for part in parts:
        if isinstance(part.root, TextPart):
            chunks.append(part.root.text)
        elif isinstance(part.root, DataPart):
            chunks.append(part.root.data)
    return "\n".join(chunks)


async def send_message(
    message: str,
    base_url: str,
    context_id: str | None = None,
    streaming=False,
    consumer: Consumer | None = None,
    max_retries: int = 3,
):
    """
    Returns dict with context_id, response and status (if exists).

    Implements exponential backoff retry logic for rate limiting (429) errors.

    Args:
        message: The message to send
        base_url: Base URL of the agent
        context_id: Optional context ID for conversation continuity
        streaming: Whether to use streaming mode
        consumer: Optional event consumer
        max_retries: Maximum number of retry attempts for rate limit errors
    """
    retry_count = 0
    base_delay = 2  # Start with 2 seconds

    while retry_count <= max_retries:
        try:
            async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as httpx_client:
                resolver = A2ACardResolver(httpx_client=httpx_client, base_url=base_url)
                agent_card = await resolver.get_agent_card()
                config = ClientConfig(
                    httpx_client=httpx_client,
                    streaming=streaming,
                )
                factory = ClientFactory(config)
                client = factory.create(agent_card)
                if consumer:
                    await client.add_event_consumer(consumer)

                outbound_msg = create_message(text=message, context_id=context_id)
                last_event = None
                outputs = {"response": "", "context_id": None}

                # if streaming == False, only one event is generated
                async for event in client.send_message(outbound_msg):
                    last_event = event

                match last_event:
                    case Message() as msg:
                        outputs["context_id"] = msg.context_id
                        outputs["response"] += merge_parts(msg.parts)

                    case (task, update):
                        outputs["context_id"] = task.context_id
                        outputs["status"] = task.status.state.value
                        msg = task.status.message
                        if msg:
                            outputs["response"] += merge_parts(msg.parts)
                        if task.artifacts:
                            for artifact in task.artifacts:
                                outputs["response"] += merge_parts(artifact.parts)

                    case _:
                        pass

                return outputs

        except Exception as e:
            error_str = str(e).lower()
            # Check if this is a rate limit error (429 or RESOURCE_EXHAUSTED)
            is_rate_limit = "429" in error_str or "resource_exhausted" in error_str or "too many requests" in error_str

            if is_rate_limit and retry_count < max_retries:
                # Calculate exponential backoff delay
                delay = base_delay * (2 ** retry_count)
                logger.warning(
                    f"Rate limit hit (429). Retrying in {delay} seconds... "
                    f"(Attempt {retry_count + 1}/{max_retries})"
                )
                await asyncio.sleep(delay)
                retry_count += 1
            else:
                # Not a rate limit error, or we've exhausted retries
                if is_rate_limit:
                    logger.error(f"Rate limit error persisted after {max_retries} retries")
                raise

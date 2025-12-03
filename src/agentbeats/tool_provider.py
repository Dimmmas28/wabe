from a2a.types import Part

from agentbeats.client import send_message


class ToolProvider:
    def __init__(self):
        self._context_ids = {}

    async def talk_to_agent(
        self,
        message: str | None = None,
        url: str | None = None,
        new_conversation: bool = False,
        parts: list[Part] | None = None,
    ):
        """
        Communicate with another agent by sending a message and receiving their response.

        Args:
            message: The text message to send (optional if parts provided)
            url: The agent's URL endpoint
            new_conversation: If True, start fresh; if False, continue existing
            parts: Optional list of Part objects for multimodal messages

        Returns:
            str: The agent's response message
        """
        # Backward compatibility: if only message provided, keep existing behavior
        outputs = await send_message(
            message=message if parts is None else None,
            base_url=url,
            context_id=None if new_conversation else self._context_ids.get(url, None),
            parts=parts,
        )
        if outputs.get("status", "completed") != "completed":
            raise RuntimeError(f"{url} responded with: {outputs}")
        self._context_ids[url] = outputs.get("context_id", None)
        return outputs["response"]

    def reset(self):
        self._context_ids = {}

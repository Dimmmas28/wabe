"""
White Agent Registry - Pluggable directory convention for white agents.

Each agent is a standalone Python file with a main() entry point that serves
an A2A-compatible agent via uvicorn. Agents share the create_agent_card()
helper for consistent agent card creation.

Available agents:
    - adk_default: Google ADK Agent with Gemini Flash (original white agent)
    - reliability: Deterministic replay agent for benchmark reliability testing
    - langgraph: LangGraph ReAct agent (WIP - needs refactor for Docker/leaderboard)
"""

import argparse
import asyncio
import logging
import random
from collections.abc import AsyncGenerator
from functools import wraps
from typing import Any, Callable

from a2a.types import AgentCapabilities, AgentCard
from google.adk.models import BaseLlm, Gemini
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse

logger = logging.getLogger(__name__)


def retry_on_rate_limit(
    max_retries: int = 5,
    base_delay: float = 2.0,
    max_delay: float = 60.0,
    jitter: float = 0.5,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Decorator for retrying async functions on rate limit errors (429).

    Uses exponential backoff with jitter to handle API rate limits gracefully.

    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay in seconds
        max_delay: Maximum delay between retries
        jitter: Random jitter factor (0-1) to add to delays

    Returns:
        Decorated function with retry logic
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception: Exception | None = None

            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    error_str = str(e).lower()
                    is_rate_limit = (
                        "429" in error_str
                        or "resource_exhausted" in error_str
                        or "rate" in error_str
                        and "limit" in error_str
                        or "quota" in error_str
                    )

                    if not is_rate_limit or attempt == max_retries:
                        raise

                    last_exception = e

                    # Exponential backoff with jitter
                    delay = min(base_delay * (2**attempt), max_delay)
                    delay += random.uniform(0, delay * jitter)

                    logger.warning(
                        f"Rate limit hit (attempt {attempt + 1}/{max_retries + 1}), "
                        f"retrying in {delay:.1f}s: {str(e)[:100]}"
                    )
                    await asyncio.sleep(delay)

            # Should not reach here, but just in case
            if last_exception:
                raise last_exception
            raise RuntimeError("Retry loop exited unexpectedly")

        return wrapper

    return decorator


class RetryGemini(BaseLlm):
    """
    Gemini LLM wrapper with automatic retry on rate limit errors.

    Wraps the standard Gemini model with exponential backoff retry logic
    to handle 429 rate limit errors gracefully.
    """

    model: str
    max_retries: int = 5
    base_delay: float = 60.0
    max_delay: float = 120.0
    jitter: float = 0.5
    _inner: Gemini | None = None

    def model_post_init(self, __context: Any) -> None:
        """Initialize the inner Gemini model after pydantic initialization."""
        self._inner = Gemini(model=self.model)

    @classmethod
    def supported_models(cls) -> list[str]:
        """Return supported model patterns."""
        return Gemini.supported_models()

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        """Generate content with retry logic for rate limits."""
        if self._inner is None:
            self._inner = Gemini(model=self.model)

        last_exception: Exception | None = None

        for attempt in range(self.max_retries + 1):
            try:
                async for response in self._inner.generate_content_async(
                    llm_request, stream=stream
                ):
                    yield response
                return  # Success, exit retry loop
            except Exception as e:
                error_str = str(e).lower()
                is_rate_limit = (
                    "429" in error_str
                    or "resource_exhausted" in error_str
                    or ("rate" in error_str and "limit" in error_str)
                    or "quota" in error_str
                )

                if not is_rate_limit or attempt == self.max_retries:
                    raise

                last_exception = e

                # Exponential backoff with jitter
                delay = min(self.base_delay * (2**attempt), self.max_delay)
                delay += random.uniform(0, delay * self.jitter)

                logger.warning(
                    f"Rate limit hit (attempt {attempt + 1}/{self.max_retries + 1}), "
                    f"retrying in {delay:.1f}s: {str(e)[:100]}"
                )
                await asyncio.sleep(delay)

        if last_exception:
            raise last_exception


def create_agent_card(
    name: str,
    description: str,
    host: str,
    port: int,
    card_url: str | None = None,
    input_modes: list[str] | None = None,
    output_modes: list[str] | None = None,
) -> AgentCard:
    """
    Create a standard agent card for a white agent.

    Args:
        name: Agent name identifier
        description: Human-readable description of the agent
        host: Host the agent is bound to
        port: Port the agent is bound to
        card_url: Optional external URL for the agent card
        input_modes: Input modes (default: ["text", "image"])
        output_modes: Output modes (default: ["text"])

    Returns:
        AgentCard configured for this agent
    """
    return AgentCard(
        name=name,
        description=description,
        url=card_url or f"http://{host}:{port}/",
        version="1.0.0",
        default_input_modes=input_modes or ["text", "image"],
        default_output_modes=output_modes or ["text"],
        capabilities=AgentCapabilities(streaming=True),
        skills=[],
    )


def create_base_arg_parser(description: str) -> argparse.ArgumentParser:
    """
    Create a standard argument parser for white agents.

    Args:
        description: Description for the argument parser

    Returns:
        ArgumentParser with --host, --port, --card-url arguments
    """
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "--host", type=str, default="127.0.0.1", help="Host to bind the server"
    )
    parser.add_argument(
        "--port", type=int, default=9019, help="Port to bind the server"
    )
    parser.add_argument(
        "--card-url", type=str, help="External URL to provide in the agent card"
    )
    return parser

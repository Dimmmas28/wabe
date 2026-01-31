import base64
import io
import logging
import os
import random
import time

from google.api_core.exceptions import ResourceExhausted, ServiceUnavailable
from langchain_google_genai import ChatGoogleGenerativeAI

logger = logging.getLogger(__name__)


def encode_image(image):
    """Convert a PIL image to base64 string."""
    if image.mode == "RGBA":
        image = image.convert("RGB")
    buffered = io.BytesIO()
    image.save(buffered, format="JPEG")
    return base64.b64encode(buffered.getvalue()).decode("utf-8")


def extract_predication(response, mode):
    """Extract the prediction from the response."""
    if mode == "Autonomous_eval":
        try:
            if "success" in response.lower().split("status:")[1]:
                return 1
            else:
                return 0
        except:
            return 0
    elif mode == "AgentTrek_eval":
        try:
            if "success" in response.lower().split("status:")[1]:
                return 1
            else:
                return 0
        except:
            return 0
    elif mode == "WebVoyager_eval":
        if "FAILURE" in response:
            return 0
        else:
            return 1
    elif mode == "WebJudge_Online_Mind2Web_eval":
        try:
            if "success" in response.lower().split("status:")[1]:
                return 1
            else:
                return 0
        except:
            return 0
    elif mode == "WebJudge_general_eval":
        try:
            if "success" in response.lower().split("status:")[1]:
                return 1
            else:
                return 0
        except:
            return 0
    else:
        raise ValueError(f"Unknown mode: {mode}")


class OpenaiEngine:
    def __init__(
        self,
        api_key=None,
        stop=[],
        rate_limit=-1,
        model=None,
        tokenizer=None,
        temperature=0,
        port=-1,
        endpoint_target_uri="",
        **kwargs,
    ) -> None:
        """Init an OpenAI GPT/Codex engine

        Args:
            api_key (_type_, optional): Auth key from OpenAI. Defaults to None.
            stop (list, optional): Tokens indicate stop of sequence. Defaults to ["\n"].
            rate_limit (int, optional): Max number of requests per minute. Defaults to -1.
            model (_type_, optional): Model family. Defaults to None.
        """
        assert (
            os.getenv("OPENAI_API_KEY", api_key) is not None
        ), "must pass on the api_key or set OPENAI_API_KEY in the environment"
        if api_key is None:
            api_key = os.getenv("OPENAI_API_KEY", api_key)
        if isinstance(api_key, str):
            self.api_keys = [api_key]
        elif isinstance(api_key, list):
            self.api_keys = api_key
        else:
            raise ValueError("api_key must be a string or list")
        self.stop = stop
        self.temperature = temperature
        self.model = model
        # convert rate limit to minmum request interval
        self.request_interval = 0 if rate_limit == -1 else 60.0 / rate_limit
        self.next_avil_time = [0] * len(self.api_keys)
        self.client = ChatGoogleGenerativeAI

        # OpenAI(
        #     api_key=api_key,
        # )

    def generate(
        self,
        messages,
        max_new_tokens=512,
        temperature=0,
        model=None,
        max_retries=5,
        base_delay=60.0,
        max_delay=120.0,
        **kwargs,
    ):
        """
        Generate a response with retry logic for rate limit handling.

        Args:
            messages: The messages to send to the model
            max_new_tokens: Maximum tokens in response
            temperature: Sampling temperature
            model: Model name (currently ignored, uses gemini-2.5-flash)
            max_retries: Maximum number of retry attempts on rate limit
            base_delay: Base delay in seconds for exponential backoff
            max_delay: Maximum delay between retries
            **kwargs: Additional arguments passed to the model

        Returns:
            List containing the response content
        """
        # Add inter-request delay to respect rate limits
        if self.request_interval > 0:
            time.sleep(self.request_interval)

        llm = self.client(
            model="gemini-2.5-flash",
            temperature=temperature,
            top_p=0.0,
            top_k=1,
            max_tokens=max_new_tokens,
            **kwargs,
        )

        last_exception = None
        for attempt in range(max_retries + 1):
            try:
                response = llm.invoke(messages)
                return [response.content]

            except (ResourceExhausted, ServiceUnavailable) as e:
                last_exception = e
                if attempt == max_retries:
                    logger.error(
                        f"RATE LIMIT ERROR: Failed after {max_retries + 1} attempts. "
                        f"The evaluation may be incomplete. Error: {e}"
                    )
                    raise

                # Exponential backoff with jitter
                delay = min(base_delay * (2**attempt), max_delay)
                jitter = random.uniform(0, delay * 0.5)
                total_delay = delay + jitter

                logger.warning(
                    f"RATE LIMIT HIT (attempt {attempt + 1}/{max_retries + 1}): "
                    f"Retrying in {total_delay:.1f}s. Error: {str(e)[:100]}"
                )
                time.sleep(total_delay)

            except Exception as e:
                # Check if it's a rate limit error in disguise
                error_str = str(e).lower()
                is_rate_limit = (
                    "429" in error_str
                    or "resource_exhausted" in error_str
                    or "quota" in error_str
                    or ("rate" in error_str and "limit" in error_str)
                )

                if is_rate_limit and attempt < max_retries:
                    last_exception = e
                    delay = min(base_delay * (2**attempt), max_delay)
                    jitter = random.uniform(0, delay * 0.5)
                    total_delay = delay + jitter

                    logger.warning(
                        f"RATE LIMIT HIT (attempt {attempt + 1}/{max_retries + 1}): "
                        f"Retrying in {total_delay:.1f}s. Error: {str(e)[:100]}"
                    )
                    time.sleep(total_delay)
                else:
                    logger.error(f"EVALUATION ERROR: Non-retryable error: {e}")
                    raise

        # Should not reach here, but just in case
        if last_exception:
            raise last_exception
        raise RuntimeError("Retry loop exited unexpectedly")

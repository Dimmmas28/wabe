"""Response parser utilities for parsing white agent responses."""

import json
import logging
from typing import Any, Dict

from utils.common_utils import parse_tags

logger = logging.getLogger(__name__)


def parse_white_agent_response(response_text: str) -> Dict[str, Any]:
    """
    Parse white agent response to extract action.

    Supports two formats:

    1. JSON format:
       <json>
       {
           "thought": "reasoning",
           "tool": "click",
           "params": {"selector": "button#submit"}
       }
       </json>

    2. Structured text format:
       THOUGHT: reasoning about what to do
       ACTION: tool_name
       PARAMS: {"param1": "value1", "param2": "value2"}

    Args:
        response_text: Raw response text from white agent

    Returns:
        Dictionary with keys:
        - thought: Agent's reasoning (optional)
        - tool: Tool/action name (defaults to "finish" if not found)
        - params: Parameters for the tool (defaults to empty dict)
    """

    # Try to parse JSON tags first
    try:
        tags = parse_tags(response_text)
        if "json" in tags:
            action_dict = json.loads(tags["json"])
            logger.debug(f"Parsed JSON format: {action_dict}")
            return action_dict
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        logger.debug(f"Failed to parse JSON format: {e}")

    # Try to parse structured text format
    try:
        lines = response_text.strip().split("\n")
        result = {}

        for line in lines:
            line = line.strip()
            if line.startswith("THOUGHT:"):
                result["thought"] = line.replace("THOUGHT:", "").strip()
            elif line.startswith("ACTION:") or line.startswith("TOOL:"):
                result["tool"] = (
                    line.replace("ACTION:", "").replace("TOOL:", "").strip()
                )
            elif line.startswith("PARAMS:"):
                params_str = line.replace("PARAMS:", "").strip()
                result["params"] = json.loads(params_str)

        if result:
            logger.debug(f"Parsed structured text format: {result}")
            return result
    except (json.JSONDecodeError, ValueError) as e:
        logger.debug(f"Failed to parse structured text format: {e}")

    # Default: unparseable response - return error for feedback/retry
    # This allows the green agent to provide feedback to the white agent to retry with correct format
    logger.warning(
        f"Could not parse white agent response, will provide feedback for retry. Got: {response_text[:500]}"
    )
    return {
        "thought": f"PARSE ERROR: Could not understand response format. Expected JSON with <json> tags or structured text (THOUGHT:/ACTION:/PARAMS:). Raw response: {response_text[:200]}",
        "tool": "error",
        "params": {
            "error_type": "parse_failure",
            "raw_response": response_text[:1000],  # Include more context for debugging
        },
    }

"""Shared browser automation and utility modules.

This package contains reusable components for browser automation and task execution.
"""

from shared.browser_agent import BrowserAgent
from shared.response_parser import parse_white_agent_response

__all__ = [
    "BrowserAgent",
    "parse_white_agent_response",
]

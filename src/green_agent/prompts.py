"""
Prompt templates for browser automation agent.

This module contains all prompt constants and templates used by the BrowserJudge.
Prompts are organized as class constants and methods for easy maintenance and reusability.
"""

from typing import Any, Dict, List


def build_tools_prompt(tools: List[Dict[str, Any]]) -> str:
    """
    Format MCP tools for LLM prompt.

    Args:
        tools: List of tool schemas from MCP server

    Returns:
        Formatted string describing available tools
    """
    lines = ["AVAILABLE TOOLS:"]

    for tool in tools:
        name = tool.get("name", "unknown")
        desc = tool.get("description", "No description")
        schema = tool.get("inputSchema", {})
        properties = schema.get("properties", {})
        required = schema.get("required", [])

        # Format parameters
        param_strs = []
        for pname, pschema in properties.items():
            ptype = pschema.get("type", "any")
            pdesc = pschema.get("description", "")
            req_marker = " (required)" if pname in required else ""
            param_strs.append(f"    - {pname}: {ptype}{req_marker}")
            if pdesc:
                param_strs.append(f"      {pdesc}")

        lines.append(f"\n{name}")
        lines.append(f"  Description: {desc}")
        if param_strs:
            lines.append("  Parameters:")
            lines.extend(param_strs)

    # Add format reminder
    lines.append("")
    lines.append("=" * 40)
    lines.append("RESPONSE FORMAT (required):")
    lines.append(
        "Wrap your response in <json></json> tags (NOT markdown ```json fences):"
    )
    lines.append("<json>")
    lines.append('{"thought": "...", "tool": "tool_name", "params": {...}}')
    lines.append("</json>")

    return "\n".join(lines)


def build_tools_reminder(tools: List[Dict[str, Any]]) -> str:
    """
    Build a concise tools reminder for subsequent steps.

    NOTE: This function is currently NOT used in production. The browser_judge
    now sends the full tools prompt (via build_tools_prompt) on every step to
    ensure the white agent has complete parameter documentation. This function
    is kept for potential future use cases where a minimal reminder is needed.

    Args:
        tools: List of tool schemas from MCP server

    Returns:
        Formatted string with tool names and key parameters
    """
    if not tools:
        return "AVAILABLE TOOLS: Not available"

    lines = ["REMINDER - AVAILABLE TOOLS:"]
    for tool in tools:
        name = tool.get("name", "unknown")
        schema = tool.get("inputSchema", {})
        required = schema.get("required", [])
        lines.append(
            f"  - {name} (required params: {', '.join(required) if required else 'none'})"
        )

    return "\n".join(lines)


class BrowserJudgePrompts:
    """Collection of prompt templates for web automation tasks."""

    @classmethod
    def task_run_prompt(
        cls, task_description: str, website: str, tools: List[Dict[str, Any]] = None
    ) -> str:
        """
        Generate the main task execution prompt with dynamic tools.

        Args:
            task_description: Description of the task to be performed
            website: Current website URL
            tools: List of tool schemas from MCP server (optional)

        Returns:
            Formatted prompt string
        """
        # Format tools dynamically from MCP server
        tools_section = build_tools_prompt(tools) if tools else "TOOLS: Not available"

        return f"""You are a web automation agent. Your task is:

TASK: {task_description}

You are currently on: {website}

UNDERSTANDING THE PAGE:
You will receive an accessibility snapshot of the page. Interactive elements have references like [ref=s15].
Use these refs to specify which element to interact with.

Example snapshot format:
- textbox "Search" [ref=s8]
- button "Submit" [ref=s12]
- link "Sign in" [ref=s20]

{tools_section}

CRITICAL - RESPONSE FORMAT:
You MUST respond with JSON wrapped in <json></json> tags in this EXACT format:

<json>
{{
    "thought": "Your reasoning about what to do next",
    "tool": "tool_name_from_list_above",
    "params": {{"param_name": "param_value"}}
}}
</json>

WARNING - COMMON MISTAKE:
Do NOT use markdown code fences. This is WRONG:
```json
{{"thought": "..."}}
```
The parser will REJECT responses with ```json. Use <json></json> tags ONLY.

EXAMPLES OF VALID RESPONSES:

Example 1 - Type text (given snapshot shows: textbox "Search" [ref=s8]):
<json>
{{
    "thought": "I should enter the search term in the search box",
    "tool": "browser_type",
    "params": {{"element": "Search textbox", "ref": "s8", "text": "Las Vegas"}}
}}
</json>

Example 2 - Click button (given snapshot shows: button "Submit" [ref=s12]):
<json>
{{
    "thought": "I need to click the submit button to proceed",
    "tool": "browser_click",
    "params": {{"element": "Submit button", "ref": "s12"}}
}}
</json>

Example 3 - Select option (given snapshot shows: combobox "Category" [ref=s18]):
<json>
{{
    "thought": "I should select Theatre from the category dropdown",
    "tool": "browser_select",
    "params": {{"element": "Category combobox", "ref": "s18", "value": "Theatre"}}
}}
</json>

IMPORTANT NOTES:
- Always wrap your JSON response in <json></json> tags
- The "thought" field should explain your reasoning
- The "tool" field must match a tool name from the AVAILABLE TOOLS section above
- CRITICAL: Most tools require BOTH "element" (human-readable description) AND "ref" (snapshot reference)
  - Extract "element" from the snapshot text (e.g., "Search textbox" from: textbox "Search" [ref=s8])
  - Extract "ref" from the [ref=...] notation (e.g., "s8" from: textbox "Search" [ref=s8])
- The "params" field must match the required parameters for that tool (check the AVAILABLE TOOLS section)
- Do not include any text outside the <json></json> tags

CURRENT PAGE SNAPSHOT:
"""


def get_task_run_prompt(task_description: str, website: str) -> str:
    """
    Standalone function to generate task run prompt.
    Use this if you prefer a functional approach over class methods.
    """
    return BrowserJudgePrompts.task_run_prompt(task_description, website)

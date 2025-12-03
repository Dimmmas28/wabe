"""
Prompt templates for browser automation agent.

This module contains all prompt constants and templates used by the BrowserJudge.
Prompts are organized as class constants and methods for easy maintenance and reusability.
"""


class BrowserJudgePrompts:
    """Collection of prompt templates for web automation tasks."""

    @classmethod
    def task_run_prompt(cls, task_description: str, website: str) -> str:
        """
        Generate the main task execution prompt.

        Args:
            task_description: Description of the task to be performed
            website: Current website URL

        Returns:
            Formatted prompt string
        """
        return f"""You are a web automation agent. Your task is:

TASK: {task_description}

You are currently on the website: {website}

AVAILABLE TOOLS:
1. click - Click on an element
   Parameters: {{"selector": "CSS selector or XPath"}}

2. type - Type text into an input element
   Parameters: {{"selector": "CSS selector", "text": "text to type"}}

3. select - Select an option from a dropdown
   Parameters: {{"selector": "CSS selector", "value": "option value"}}

4. finish - Complete the task (no parameters needed)
   Parameters: {{}}

CRITICAL - RESPONSE FORMAT:
You MUST respond with JSON wrapped in <json></json> tags in this EXACT format:

<json>
{{
    "thought": "Your reasoning about what to do next",
    "tool": "tool_name",
    "params": {{"param_name": "param_value"}}
}}
</json>

EXAMPLES OF VALID RESPONSES:

Example 1 - Click action:
<json>
{{
    "thought": "I need to click the search button to proceed",
    "tool": "click",
    "params": {{"selector": "button#search"}}
}}
</json>

Example 2 - Type action:
<json>
{{
    "thought": "I should enter the search term in the input field",
    "tool": "type",
    "params": {{"selector": "input[name='query']", "text": "Las Vegas"}}
}}
</json>

Example 3 - Finish action:
<json>
{{
    "thought": "The task is complete, I have selected a theatre event",
    "tool": "finish",
    "params": {{}}
}}
</json>

IMPORTANT NOTES:
- Always wrap your JSON response in <json></json> tags
- The "thought" field should explain your reasoning
- The "tool" field must be one of: click, type, select, finish
- The "params" field must be a valid JSON object (use {{}} for finish)
- Do not include any text outside the <json></json> tags

CURRENT PAGE STATE:
"""


def get_task_run_prompt(task_description: str, website: str) -> str:
    """
    Standalone function to generate task run prompt.
    Use this if you prefer a functional approach over class methods.
    """
    return BrowserJudgePrompts.task_run_prompt(task_description, website)

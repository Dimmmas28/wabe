"""
ReAct Pattern Web Agent using LangGraph

This agent implements the ReAct (Reasoning + Acting) pattern for web browser
navigation tasks using LangGraph's stateful graph workflow.

The agent follows a think→act→observe loop:
1. Reason: Use LLM to analyze current state and decide next action
2. Act: Execute the chosen browser action
3. Observe: Process results and update state

This implementation maintains compatibility with the A2A protocol and can be
used as a drop-in replacement for the original white_agent.py.
"""

import argparse
import json
import logging
from typing import Annotated, Any, Literal, TypedDict

import uvicorn
from dotenv import load_dotenv
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

load_dotenv()

from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore, TaskUpdater
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    Part,
    TaskState,
    TextPart,
)
from a2a.utils import new_agent_text_message

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# ==============================================================================
# State Definition
# ==============================================================================


class AgentState(TypedDict):
    """
    State for the ReAct agent.
    
    This state is maintained throughout the agent's execution and updated
    at each step of the think→act→observe loop.
    """
    
    # Conversation history (includes user messages and agent responses)
    messages: Annotated[list[BaseMessage], add_messages]
    
    # Current page snapshot (accessibility tree)
    current_snapshot: str
    
    # Available browser tools from MCP
    available_tools: list[dict[str, Any]]
    
    # Current iteration's reasoning
    thought: str
    
    # Chosen action for current iteration
    action: dict[str, Any]  # {"tool": str, "params": dict}
    
    # Observation from last action execution
    observation: str
    
    # Iteration counter (for max steps check)
    iteration: int


# ==============================================================================
# ReAct Prompt Template
# ==============================================================================


def build_react_prompt(
    task_description: str,
    available_tools: list[dict[str, Any]],
    current_snapshot: str,
    previous_thought: str = "",
    previous_observation: str = "",
) -> str:
    """
    Build a ReAct-style prompt for the reasoning node.
    
    This prompt guides the LLM to think step-by-step and choose appropriate
    actions based on the current state of the browser.
    """
    
    # Format available tools
    tools_desc = []
    for tool in available_tools:
        tool_name = tool.get("name", "unknown")
        tool_description = tool.get("description", "")
        schema = tool.get("inputSchema", {})
        required = schema.get("required", [])
        properties = schema.get("properties", {})
        
        params_desc = []
        for param_name, param_schema in properties.items():
            param_type = param_schema.get("type", "any")
            param_desc = param_schema.get("description", "")
            is_required = param_name in required
            req_marker = " (REQUIRED)" if is_required else " (optional)"
            params_desc.append(f"    - {param_name}: {param_type}{req_marker} - {param_desc}")
        
        tool_block = f"{tool_name}:\n  {tool_description}\n  Parameters:\n" + "\n".join(params_desc)
        tools_desc.append(tool_block)
    
    tools_section = "\n\n".join(tools_desc)
    
    # Build context from previous iteration
    context_section = ""
    if previous_thought and previous_observation:
        context_section = f"""
PREVIOUS ITERATION:
Thought: {previous_thought}
Observation: {previous_observation}
"""
    
    prompt = f"""You are a web automation agent using the ReAct pattern.

TASK: {task_description}

AVAILABLE TOOLS:
{tools_section}

finish:
  Call this when you have completed the task successfully.
  Parameters:
    - reason: str (REQUIRED) - Explanation of why the task is complete

{context_section}
CURRENT PAGE SNAPSHOT:
{current_snapshot}

Follow the ReAct pattern:
1. THINK: Analyze the current state and reason about what to do next
2. ACT: Choose ONE tool to execute with appropriate parameters

You MUST respond with valid JSON in the following format wrapped in <json></json> tags:

<json>
{{
  "thought": "Your step-by-step reasoning about what to do next",
  "tool": "tool_name",
  "params": {{
    "param1": "value1",
    "param2": "value2"
  }}
}}
</json>

Important guidelines:
- Most interactive tools require BOTH "element" (description) and "ref" (snapshot reference like "s8")
- Always look at the snapshot to find the correct ref for the element you want to interact with
- Think carefully about which action will make progress toward the task goal
- Use "finish" when the task is complete
- Make sure your JSON is properly formatted with double quotes

Now, think step-by-step and decide what to do next:"""
    
    return prompt


# ==============================================================================
# Graph Nodes
# ==============================================================================


def reason_node(state: AgentState) -> AgentState:
    """
    Reasoning node: Use LLM to analyze current state and decide next action.
    
    This implements the "Think" part of the ReAct pattern.
    """
    logger.info(f"=== REASON NODE (Iteration {state['iteration']}) ===")
    
    # Get the last message which contains task info
    messages = state["messages"]
    last_message = messages[-1] if messages else None
    
    # Extract task from initial message
    task_description = "Complete the web task"
    if last_message and isinstance(last_message, HumanMessage):
        # Parse out task from message content
        content = last_message.content if isinstance(last_message.content, str) else ""
        if "TASK:" in content:
            task_description = content.split("TASK:")[1].split("\n")[0].strip()
    
    # Build ReAct prompt
    prompt = build_react_prompt(
        task_description=task_description,
        available_tools=state["available_tools"],
        current_snapshot=state["current_snapshot"],
        previous_thought=state.get("thought", ""),
        previous_observation=state.get("observation", ""),
    )
    
    # Create LLM instance
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash-exp",
        temperature=0.0,
        top_p=0.95,
    )
    
    # Get LLM response
    response = llm.invoke([SystemMessage(content=prompt)])
    response_text = response.content
    
    logger.info(f"LLM Response:\n{response_text}")
    
    # Parse response
    try:
        # Extract JSON from tags
        if "<json>" in response_text and "</json>" in response_text:
            json_str = response_text.split("<json>")[1].split("</json>")[0].strip()
            parsed = json.loads(json_str)
        else:
            # Try to parse the whole response as JSON
            parsed = json.loads(response_text)
        
        thought = parsed.get("thought", "No thought provided")
        tool = parsed.get("tool", "finish")
        params = parsed.get("params", {})
        
        logger.info(f"Thought: {thought}")
        logger.info(f"Action: {tool} with params {params}")
        
        # Update state
        state["thought"] = thought
        state["action"] = {"tool": tool, "params": params}
        
    except (json.JSONDecodeError, KeyError, IndexError) as e:
        logger.error(f"Failed to parse LLM response: {e}")
        logger.error(f"Response was: {response_text[:500]}")
        
        # Fallback: finish with error
        state["thought"] = f"Error parsing response: {e}"
        state["action"] = {
            "tool": "finish",
            "params": {"reason": "Error in reasoning, terminating"}
        }
    
    return state


def act_node(state: AgentState) -> AgentState:
    """
    Action node: Execute the chosen action and record observation.
    
    This implements the "Act" and "Observe" parts of the ReAct pattern.
    Note: The actual tool execution happens in the A2A handler; this node
    just formats the response for the next iteration.
    """
    logger.info("=== ACT NODE ===")
    
    action = state["action"]
    tool = action.get("tool", "finish")
    params = action.get("params", {})
    
    # Format observation
    if tool == "finish":
        observation = f"Task completed: {params.get('reason', 'No reason provided')}"
    else:
        # Create observation that will be updated after actual execution
        observation = f"Executed {tool} with parameters {params}"
    
    logger.info(f"Observation: {observation}")
    
    state["observation"] = observation
    state["iteration"] += 1
    
    return state


def should_continue(state: AgentState) -> Literal["continue", "end"]:
    """
    Conditional edge: Determine whether to continue the loop or end.
    
    Returns:
        "end" if finish action is selected
        "continue" to loop back to reasoning
    """
    action = state["action"]
    tool = action.get("tool", "finish")
    
    if tool == "finish":
        logger.info("=== ENDING: Finish action selected ===")
        return "end"
    
    # Also check max iterations (safety)
    max_iterations = 20
    if state["iteration"] >= max_iterations:
        logger.warning(f"=== ENDING: Max iterations ({max_iterations}) reached ===")
        return "end"
    
    logger.info("=== CONTINUING: Looping back to reasoning ===")
    return "continue"


# ==============================================================================
# Graph Construction
# ==============================================================================


def create_react_graph() -> StateGraph:
    """
    Create the ReAct workflow graph.
    
    Graph structure:
        START → reason_node → act_node → should_continue
                                 ↑              ↓
                                 └──(continue)──┘
                                        ↓
                                      (end)
                                        ↓
                                      END
    """
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("reason", reason_node)
    workflow.add_node("act", act_node)
    
    # Add edges
    workflow.add_edge(START, "reason")
    workflow.add_edge("reason", "act")
    
    # Conditional edge from act
    workflow.add_conditional_edges(
        "act",
        should_continue,
        {
            "continue": "reason",
            "end": END,
        },
    )
    
    return workflow.compile()


# ==============================================================================
# A2A Integration
# ==============================================================================


class ReActAgentRequestHandler(DefaultRequestHandler):
    """
    Custom request handler that integrates the ReAct graph with A2A protocol.
    """
    
    def __init__(self):
        super().__init__()
        self.graph = create_react_graph()
        self.conversation_states: dict[str, dict] = {}
        logger.info("ReActAgentRequestHandler initialized")
    
    async def handle_task(
        self,
        task_id: str,
        parts: list[Part],
        updater: TaskUpdater,
    ):
        """Handle incoming task from green agent."""
        logger.info(f"Handling task {task_id}")
        
        # Extract text and parse request
        text_content = ""
        for part in parts:
            if isinstance(part.root, TextPart):
                text_content += part.root.text + "\n"
        
        logger.info(f"Received content:\n{text_content[:500]}...")
        
        # Parse the request to extract snapshot and tools
        snapshot = self._extract_snapshot(text_content)
        tools = self._extract_tools(text_content)
        
        # Initialize or get conversation state
        if task_id not in self.conversation_states:
            logger.info(f"New conversation for task {task_id}")
            self.conversation_states[task_id] = {
                "messages": [HumanMessage(content=text_content)],
                "current_snapshot": snapshot,
                "available_tools": tools,
                "thought": "",
                "action": {},
                "observation": "",
                "iteration": 0,
            }
        else:
            # Update state for continuing conversation
            logger.info(f"Continuing conversation for task {task_id}")
            self.conversation_states[task_id]["current_snapshot"] = snapshot
            self.conversation_states[task_id]["messages"].append(
                HumanMessage(content=text_content)
            )
        
        # Run the graph
        state = self.conversation_states[task_id]
        result_state = self.graph.invoke(state)
        
        # Update stored state
        self.conversation_states[task_id] = result_state
        
        # Format response
        thought = result_state.get("thought", "No thought")
        action = result_state.get("action", {})
        
        response_json = {
            "thought": thought,
            "tool": action.get("tool", "finish"),
            "params": action.get("params", {}),
        }
        
        response_text = f"<json>\n{json.dumps(response_json, indent=2)}\n</json>"
        
        logger.info(f"Sending response:\n{response_text}")
        
        # Send response
        await updater.update_status(
            TaskState.working,
            new_agent_text_message(response_text),
        )
    
    def _extract_snapshot(self, text: str) -> str:
        """Extract page snapshot from request text."""
        if "CURRENT PAGE SNAPSHOT:" in text:
            snapshot = text.split("CURRENT PAGE SNAPSHOT:")[1]
            # Clean up truncation marker if present
            if "[Snapshot truncated" in snapshot:
                snapshot = snapshot.split("[Snapshot truncated")[0]
            return snapshot.strip()
        return ""
    
    def _extract_tools(self, text: str) -> list[dict[str, Any]]:
        """
        Extract available tools from request text.
        
        Note: This is a simplified parser. In production, tools would be
        passed via a structured format or stored from initial setup.
        """
        tools = []
        
        # Add common browser tools (these match MCP browser tools)
        tools.append({
            "name": "browser_click",
            "description": "Click on an element",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "element": {"type": "string", "description": "Human-readable element description"},
                    "ref": {"type": "string", "description": "Snapshot reference (e.g., s8)"},
                },
                "required": ["element", "ref"],
            },
        })
        
        tools.append({
            "name": "browser_type",
            "description": "Type text into an element",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "element": {"type": "string", "description": "Human-readable element description"},
                    "ref": {"type": "string", "description": "Snapshot reference (e.g., s8)"},
                    "text": {"type": "string", "description": "Text to type"},
                },
                "required": ["element", "ref", "text"],
            },
        })
        
        tools.append({
            "name": "browser_select",
            "description": "Select an option from a dropdown",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "element": {"type": "string", "description": "Human-readable element description"},
                    "ref": {"type": "string", "description": "Snapshot reference (e.g., s8)"},
                    "value": {"type": "string", "description": "Value to select"},
                },
                "required": ["element", "ref", "value"],
            },
        })
        
        tools.append({
            "name": "browser_scroll",
            "description": "Scroll the page",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "direction": {"type": "string", "description": "Direction to scroll (up/down)"},
                },
                "required": ["direction"],
            },
        })
        
        return tools


def browser_agent_card(host: str, port: int, card_url: str = None) -> AgentCard:
    """Create the agent card for the ReAct browser navigation agent."""
    return AgentCard(
        name="react_browser_agent",
        description="A ReAct-based web browser navigation agent that uses reasoning and acting loops to complete web tasks.",
        url=card_url or f"http://{host}:{port}/",
        version="2.0.0",
        default_input_modes=["text", "image"],
        default_output_modes=["text"],
        capabilities=AgentCapabilities(streaming=True),
        skills=[],
    )


# ==============================================================================
# Main
# ==============================================================================


def main():
    parser = argparse.ArgumentParser(
        description="Run the ReAct-based A2A browser navigation white agent."
    )
    parser.add_argument(
        "--host", type=str, default="127.0.0.1", help="Host to bind the server"
    )
    parser.add_argument(
        "--port", type=int, default=9020, help="Port to bind the server"
    )
    parser.add_argument(
        "--card-url", type=str, help="External URL to provide in the agent card"
    )
    args = parser.parse_args()
    
    # Create agent card
    agent_card = browser_agent_card(args.host, args.port, args.card_url)
    
    # Create A2A application with custom handler
    task_store = InMemoryTaskStore()
    request_handler = ReActAgentRequestHandler()
    
    app = A2AStarletteApplication(
        agent_card=agent_card,
        task_store=task_store,
        request_handler=request_handler,
    )
    
    logger.info(f"Starting ReAct white agent on {args.host}:{args.port}")
    print(f"🚀 ReAct Browser Agent running on http://{args.host}:{args.port}")
    print(f"   Model: gemini-2.0-flash-exp with ReAct pattern")
    print(f"   Graph: reason → act → should_continue (loop)")
    
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()

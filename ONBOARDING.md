# WABE Onboarding Documentation

**Welcome to WABE** (Web Agent Browser Evaluation) - a browser automation benchmark for evaluating AI agents.

This document provides a comprehensive walkthrough of the WABE codebase for new team members. By the end, you'll understand how the system works from start to finish, what each component does, and how to modify it for your needs.

---

## Table of Contents

1. [Introduction & Overview](#1-introduction--overview)
2. [Understanding the A2A Protocol](#2-understanding-the-a2a-protocol)
3. [Understanding AgentBeats Framework](#3-understanding-agentbeats-framework)
4. [WABE Architecture](#4-wabe-architecture)
5. [Execution Flow Walkthrough](#5-execution-flow-walkthrough)
6. [File-by-File Code Explanation](#6-file-by-file-code-explanation)
7. [Key Concepts Deep Dive](#7-key-concepts-deep-dive)
8. [Configuration & Customization](#8-configuration--customization)
9. [Output & Logging](#9-output--logging)
10. [Common Patterns & Best Practices](#10-common-patterns--best-practices)
11. [Development Workflow](#11-development-workflow)
12. [Appendix](#12-appendix)

---

## 1. Introduction & Overview

### What is WABE?

WABE is a **benchmark system** that evaluates AI agents on their ability to navigate websites and complete realistic web tasks. It uses browser automation (Playwright) to create a real-world environment where agents interact with actual websites.

### Key Concepts

**Browser Automation Evaluation**: WABE runs a real browser, loads websites, and lets AI agents control it by clicking, typing, and selecting elements.

**AI Agents**: WABE uses two types of agents:
- **Green Agent (Judge)**: Orchestrates the evaluation, runs the browser, sends tasks to the white agent
- **White Agent (Participant)**: The AI being evaluated, receives HTML and returns actions

**A2A Protocol**: A standardized way for agents to communicate with each other using JSON messages over HTTP.

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         AgentBeats                              │
│                    (Orchestration Layer)                        │
│  • Spawns agents as subprocesses                               │
│  • Manages lifecycle (start, health check, stop)               │
│  • Multiplexes logs to files and terminal                      │
└────────────────────┬────────────────────────────────────────────┘
                     │
        ┌────────────┴────────────┐
        │                         │
┌───────▼──────────┐    ┌────────▼─────────────┐
│  Green Agent     │    │   White Agent        │
│  (Browser Judge) │◄──►│   (Gemini AI)        │
│                  │    │                      │
│  • Runs browser  │    │  • Analyzes HTML     │
│  • Sends HTML    │    │  • Returns actions   │
│  • Executes acts │    │  • Uses LLM          │
└──────┬───────────┘    └──────────────────────┘
       │
       │ uses Playwright
       │
┌──────▼───────────────────────────────────────┐
│          Browser (Chromium)                  │
│  • Loads real websites                       │
│  • Executes actions (click, type, select)    │
│  • Captures screenshots                      │
└──────────────────────────────────────────────┘
```

---

## 2. Understanding the A2A Protocol

### What is A2A?

**Agent-to-Agent (A2A)** is an open protocol that enables communication between independent AI agent systems. Think of it as a standardized API for agents to talk to each other, regardless of what framework they're built with.

### Why A2A?

Without A2A, every agent would need custom integration code. With A2A:
- ✅ Agents from different frameworks can work together
- ✅ Standardized message format (JSON-RPC over HTTP)
- ✅ Discovery mechanism (Agent Cards)
- ✅ Support for long-running tasks
- ✅ Streaming and async operations

### Core A2A Concepts

#### 1. Agent Card

An **Agent Card** is a JSON document that describes what an agent can do:

```json
{
  "name": "BrowserJudge",
  "description": "Evaluates web automation agents...",
  "url": "http://127.0.0.1:9009/",
  "version": "1.0.0",
  "skills": [...]
}
```

Agents publish their card at `/.well-known/agent-card.json`. Other agents fetch this to discover capabilities.

#### 2. Messages

Messages are the basic unit of communication:

```python
Message(
    kind="message",
    role=Role.user,  # or Role.agent
    parts=[Part(TextPart(text="Hello"))],
    message_id="unique-id",
    context_id="conversation-id"  # For multi-turn conversations
)
```

**Key fields**:
- `role`: Who's sending (user or agent)
- `parts`: Message content (text, data, or both)
- `context_id`: Links messages in a conversation

#### 3. Tasks

For long-running operations, A2A uses **Tasks**:

```python
Task(
    id="task-123",
    status=TaskState.working,  # pending, working, completed, failed
    artifacts=[...]  # Results/outputs
)
```

Tasks allow agents to:
- Report progress with status updates
- Return results as artifacts
- Handle async operations

#### 4. Context

The `context_id` enables **multi-turn conversations**:
- Same `context_id` = continuation of conversation
- New/no `context_id` = fresh conversation
- Agent maintains conversation state

### How WABE Uses A2A

**Green Agent**: Runs an A2A server that accepts evaluation requests
**White Agent**: Runs an A2A server that accepts HTML + task and returns actions
**Communication**: Both use A2A messages for all interactions

```
Client → (A2A Message with EvalRequest) → Green Agent
Green Agent → (A2A Message with HTML) → White Agent
White Agent → (A2A Message with Action) → Green Agent
```

### Learn More

- [Official A2A Specification](https://a2a-protocol.org/latest/specification/)
- [A2A GitHub Repository](https://github.com/a2aproject/A2A)
- [IBM's A2A Explainer](https://www.ibm.com/think/topics/agent2agent-protocol)

---

## 3. Understanding AgentBeats Framework

### What is AgentBeats?

**AgentBeats** is a framework for **Agentified Agent Assessment (AAA)** - the idea that evaluation itself should be handled by specialized agents.

Traditional benchmarks use static test suites. AgentBeats uses **green agents** that actively evaluate **white/purple agents** in dynamic environments.

### Key Concepts

#### Green Agents (Evaluators/Judges)

**Green agents** are the evaluators. They:
- Set up the evaluation environment (e.g., browser)
- Issue tasks to agents being evaluated
- Observe and record behavior
- Compute performance metrics
- Return evaluation results

In WABE, `browser_judge.py` is the green agent.

#### White/Purple Agents (Participants)

**White agents** are the agents being evaluated. They:
- Receive tasks from green agents
- Process inputs (e.g., HTML)
- Return actions/decisions
- Get scored on their performance

In WABE, `white_agent.py` (powered by Gemini) is the white agent.

#### Color System

- **Green**: Evaluator/judge agents
- **Purple/White**: Participants being evaluated
- This color-coding comes from Go games and was adopted by AgentBeats

### How AgentBeats Orchestrates Evaluations

```
1. Read scenario.toml configuration
2. Start white agent(s) as subprocess(es)
3. Start green agent as subprocess
4. Wait for all agents to be healthy (check agent cards)
5. Send evaluation request to green agent
6. Green agent runs evaluation, coordinates with white agent
7. Green agent returns results
8. Shutdown all agents
```

### Task Management Lifecycle

AgentBeats uses A2A tasks to track evaluation progress:

```
TaskState.pending    → Evaluation request received
TaskState.working    → Green agent is running evaluation
                       (Multiple status updates during evaluation)
TaskState.completed  → Evaluation finished, results available
```

### Why This Design?

**Reusability**: Green agents encapsulate evaluation logic. You can:
- Swap white agents to compare different AI models
- Reuse green agents across multiple benchmarks
- Share green agents with the community

**Standardization**: All agents speak A2A, so evaluations are reproducible and comparable.

### Learn More

- [AgentBeats Documentation](https://docs.agentbeats.org/)
- [Google's ADK and Agent Evaluation](https://google.github.io/adk-docs/evaluate/)

---

## 4. WABE Architecture

### Component Overview

WABE consists of four layers:

```
┌─────────────────────────────────────────────────────────────┐
│ 1. ORCHESTRATION LAYER                                      │
│    • run_scenario.py: Main entry point, spawns processes    │
│    • client_cli.py: Sends evaluation request                │
│    • scenario.toml: Configuration file                      │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. A2A COMMUNICATION LAYER                                  │
│    • client.py: A2A protocol client                         │
│    • tool_provider.py: Agent communication wrapper          │
│    • models.py: EvalRequest/EvalResult data structures      │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. AGENT FRAMEWORK LAYER                                    │
│    • green_executor.py: Green agent → A2A adapter           │
│    • browser_judge.py: Green agent implementation           │
│    • white_agent.py: White agent (Gemini LLM)               │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ 4. BROWSER AUTOMATION LAYER                                 │
│    • browser_agent.py: Playwright wrapper                   │
│    • browser_helper.py: Browser initialization              │
│    • html_cleaner.py: HTML preprocessing for LLM            │
│    • response_parser.py: Parse LLM action responses         │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow

```
┌────────────┐
│    User    │
└─────┬──────┘
      │ uv run agentbeats-run scenario.toml
      ↓
┌─────────────────────────────────────────────────────────────┐
│ run_scenario.py (Orchestrator)                              │
│ • Parse scenario.toml                                       │
│ • Spawn white_agent.py (port 9019)                          │
│ • Spawn browser_judge.py (port 9009)                        │
│ • Wait for agents to be ready                               │
│ • Spawn client_cli.py                                       │
└───────────────────┬─────────────────────────────────────────┘
                    │
                    ↓
┌─────────────────────────────────────────────────────────────┐
│ client_cli.py                                               │
│ • Create EvalRequest JSON                                   │
│ • Send to green agent via A2A                               │
└───────────────────┬─────────────────────────────────────────┘
                    │ A2A Message
                    ↓
┌─────────────────────────────────────────────────────────────┐
│ browser_judge.py (Green Agent)                              │
│                                                             │
│ ┌─ Start browser, navigate to website                      │
│ │                                                           │
│ ├─ FOR each step (1..max_steps):                           │
│ │   ├─ Get HTML from browser                               │
│ │   ├─ Clean HTML (remove scripts, styles, etc.)           │
│ │   ├─ Send HTML + task → white_agent ─────────┐           │
│ │   │                                           ↓           │
│ │   │  ┌────────────────────────────────────────────────┐  │
│ │   │  │ white_agent.py (White Agent)                   │  │
│ │   │  │ • Receive HTML + task                          │  │
│ │   │  │ • Send to Gemini 2.0 Flash LLM                 │  │
│ │   │  │ • LLM returns action JSON                      │  │
│ │   │  └────────────┬───────────────────────────────────┘  │
│ │   │               │ Action JSON                          │
│ │   ├─ Receive action ←──────────────────────┘             │
│ │   ├─ Parse action (thought, tool, params)                │
│ │   ├─ Execute action in browser (click, type, select)     │
│ │   └─ Take screenshot                                     │
│ │                                                           │
│ ├─ Save session (action history, screenshots, metadata)    │
│ └─ Return EvalResult artifact via A2A                      │
└─────────────────────┬───────────────────────────────────────┘
                      │ EvalResult
                      ↓
┌─────────────────────────────────────────────────────────────┐
│ client_cli.py                                               │
│ • Receive result                                            │
│ • Print to stdout                                           │
└─────────────────────────────────────────────────────────────┘
```

### Communication Patterns

**1. Client ↔ Green Agent**: A2A JSON messages over HTTP
- Client sends `EvalRequest` with task configuration
- Green agent streams status updates
- Green agent returns result as artifact

**2. Green Agent ↔ White Agent**: A2A JSON messages over HTTP
- Green agent sends HTML + task description
- White agent returns action JSON
- Uses `context_id` for multi-turn conversation

**3. Green Agent ↔ Browser**: Playwright async API
- Direct Python function calls (not HTTP)
- Browser actions return success/failure

---

## 5. Execution Flow Walkthrough

Let's trace what happens when you run:

```bash
uv run agentbeats-run scenarios/web_browser/scenario.toml
```

### Step 1: Entry Point (`run_scenario.py:main()`)

**File**: `src/agentbeats/run_scenario.py:151-308`

```python
def main():
    # Parse CLI arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("scenario", help="Path to scenario TOML file")
    args = parser.parse_args()

    # Parse scenario.toml
    cfg = parse_toml(args.scenario)
```

**What happens**:
1. Parse command-line arguments
2. Read and parse `scenario.toml` (line 111-148)
3. Extract green agent config, white agent config, and task config

### Step 2: Log File Setup

**File**: `src/agentbeats/run_scenario.py:168-176`

```python
# Create timestamped log files
timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
log_dir = get_log_dir()  # .logs/ directory

# Setup TeeFile for multiplexing output
# Writes to both log file AND stdout/stderr
```

**What happens**:
1. Create `.logs/` directory if it doesn't exist
2. Generate timestamp for log file names
3. Prepare `TeeFile` objects that write to both files and terminal

**Pattern**: `TeeFile` (line 33-59) is a clever multiplexer that writes to multiple file handles simultaneously, ensuring logs are saved even when displayed in terminal.

### Step 3: Start White Agent

**File**: `src/agentbeats/run_scenario.py:183-211`

```python
# Start participant agents
for p in cfg["participants"]:
    cmd_args = shlex.split(p.get("cmd", ""))
    if cmd_args:
        # "python scenarios/web_browser/white_agent.py --host 127.0.0.1 --port 9019"
        procs.append(subprocess.Popen(cmd_args, ...))
```

**What happens**:
1. For each participant in scenario.toml (the white agent)
2. Parse command from config: `python scenarios/web_browser/white_agent.py --host 127.0.0.1 --port 9019`
3. Spawn subprocess with `Popen`
4. Connect stdout/stderr to log file (and optionally terminal)

**White agent startup** (`scenarios/web_browser/white_agent.py:36-95`):
```python
def main():
    # Create Google ADK agent with Gemini model
    root_agent = Agent(
        name="browser_agent",
        model="gemini-2.0-flash-exp",
        instruction="You are a helpful web automation agent..."
    )

    # Create agent card
    agent_card = browser_agent_card(args.host, args.port)

    # Convert to A2A protocol and run
    a2a_app = to_a2a(root_agent, agent_card=agent_card)
    uvicorn.run(a2a_app, host=args.host, port=args.port)
```

Now white agent is listening on `http://127.0.0.1:9019`

### Step 4: Start Green Agent

**File**: `src/agentbeats/run_scenario.py:213-241`

```python
# Start green agent
green_cmd_args = shlex.split(cfg["green_agent"].get("cmd", ""))
# "python scenarios/web_browser/browser_judge.py --host 127.0.0.1 --port 9009"
procs.append(subprocess.Popen(green_cmd_args, ...))
```

**Green agent startup** (`scenarios/web_browser/browser_judge.py:368-431`):
```python
async def main():
    # Create BrowserJudge agent
    agent = BrowserJudge()

    # Wrap in GreenExecutor (A2A adapter)
    executor = GreenExecutor(agent)

    # Create agent card
    agent_card = browser_judge_agent_card("BrowserJudge", agent_url)

    # Create A2A server with request handler
    request_handler = DefaultRequestHandler(
        agent_executor=executor,
        task_store=InMemoryTaskStore()
    )
    server = A2AStarletteApplication(agent_card=agent_card, http_handler=request_handler)

    # Start uvicorn
    uvicorn.run(server.build(), host=args.host, port=args.port)
```

Now green agent is listening on `http://127.0.0.1:9009`

### Step 5: Wait for Agents to Be Ready

**File**: `src/agentbeats/run_scenario.py:62-108`

```python
async def wait_for_agents(cfg: dict, timeout: int = 30) -> bool:
    endpoints = [...]  # Collect all agent endpoints

    while time.time() - start_time < timeout:
        for endpoint in endpoints:
            # Try to fetch agent card
            resolver = A2ACardResolver(httpx_client=client, base_url=endpoint)
            await resolver.get_agent_card()

        if ready_count == len(endpoints):
            return True  # All agents ready!
```

**What happens**:
1. Try to fetch agent card from each endpoint
2. If fetch succeeds, agent is ready
3. Poll every 1 second until all agents are ready or timeout (30s)

**Why**: Agents take a few seconds to start uvicorn servers. This ensures they're fully initialized before proceeding.

### Step 6: Start Client CLI

**File**: `src/agentbeats/run_scenario.py:257-278`

```python
client_proc = subprocess.Popen(
    [sys.executable, "-m", "agentbeats.client_cli", args.scenario],
    ...
)
client_proc.wait()  # Wait for client to finish
```

**Client startup** (`src/agentbeats/client_cli.py`):
```python
def main():
    cfg = parse_toml(sys.argv[1])

    # Build EvalRequest
    req = EvalRequest(
        participants={"white_agent": "http://127.0.0.1:9019"},
        config={
            "task_id": "...",
            "website": "https://www.stubhub.com/",
            "task": "Show theatre events for Las Vegas...",
            "max_steps": 10
        }
    )

    # Send to green agent
    outputs = await send_message(
        message=req.model_dump_json(),
        base_url="http://127.0.0.1:9009"
    )
```

### Step 7: Green Agent Receives Request

**File**: `src/agentbeats/green_executor.py:31-71`

```python
class GreenExecutor(AgentExecutor):
    async def execute(self, context: RequestContext, event_queue: EventQueue):
        # Parse incoming message as EvalRequest
        req: EvalRequest = EvalRequest.model_validate_json(context.get_user_input())

        # Validate request
        ok, msg = self.agent.validate_request(req)

        # Create task
        task = new_task(msg)
        await event_queue.enqueue_event(task)

        # Create updater for sending status updates
        updater = TaskUpdater(event_queue, task.id, task.context_id)

        # Run the evaluation!
        await self.agent.run_eval(req, updater)
        await updater.complete()
```

**Pattern**: `GreenExecutor` is an **adapter** that bridges the A2A protocol and custom green agent logic. It handles:
- Parsing A2A messages
- Creating tasks
- Providing `TaskUpdater` for status updates
- Error handling

### Step 8: Browser Judge Runs Evaluation

**File**: `scenarios/web_browser/browser_judge.py:92-320`

This is the core evaluation logic. Let's break it down:

#### 8a. Initialize Browser

```python
async def run_eval(self, req: EvalRequest, updater: TaskUpdater):
    # Extract config
    white_agent_url = req.participants["white_agent"]
    task_id = req.config["task_id"]
    website = req.config["website"]
    task_description = req.config["task"]
    max_steps = req.config["max_steps"]

    # Create browser agent
    browser_agent = BrowserAgent(headless=False, output_dir=f".output/browser_eval_{task_id}")

    # Start browser and navigate
    await browser_agent.start(website)
```

**`BrowserAgent.start()`** (`src/shared/browser_agent.py:114-143`):
```python
async def start(self, url: str):
    # Launch Playwright
    playwright = await async_playwright().start()
    self.browser = await normal_launch_async(playwright, headless=self.headless)

    # Create context (viewport 1280x720)
    context = await normal_new_context_async(self.browser)

    # Create page and navigate
    await context.new_page()
    await self.page.goto(url, wait_until="load")

    # Take initial screenshot
    await self.take_screenshot("initial")
```

#### 8b. Main Evaluation Loop

```python
for step in range(max_steps):
    # Get current page HTML
    html = await browser_agent.get_html(cleaned=True, format="html")

    # Truncate if too long (max 20000 chars for LLM context)
    html_truncated = html[:20000]

    # Prepare message for white agent
    if step == 0:
        message = initial_prompt + f"\n\nCURRENT HTML:\n{html_truncated}"
    else:
        message = f"CURRENT HTML:\n{html_truncated}\n\nWhat should we do next?"
```

**HTML Cleaning** (`src/shared/html_cleaner.py`):
- Removes: `<script>`, `<style>`, `<svg>`, `<iframe>`, etc.
- Keeps: Interactive elements (`<a>`, `<button>`, `<input>`, etc.)
- Simplifies: Text truncated to 200 chars per element
- Result: Cleaned HTML that fits in LLM context window

#### 8c. Communicate with White Agent

```python
    # Send to white agent
    response_text = await self._tool_provider.talk_to_agent(
        message=message,
        url=white_agent_url,
        new_conversation=(step == 0)
    )
```

**`ToolProvider.talk_to_agent()`** (`src/agentbeats/tool_provider.py:8-30`):
```python
async def talk_to_agent(self, message: str, url: str, new_conversation: bool = False):
    outputs = await send_message(
        message=message,
        base_url=url,
        context_id=None if new_conversation else self._context_ids.get(url, None)
    )
    # Save context_id for next message
    self._context_ids[url] = outputs.get("context_id", None)
    return outputs["response"]
```

**Pattern**: `ToolProvider` maintains a **context map** `{url → context_id}` to enable multi-turn conversations. First message has `context_id=None` (new conversation), subsequent messages reuse the same `context_id`.

**White Agent Processing**:
1. Receives HTML + task from green agent
2. Sends to Gemini 2.0 Flash LLM
3. LLM analyzes HTML and decides next action
4. Returns JSON: `{"thought": "...", "tool": "click", "params": {"selector": "..."}}`

#### 8d. Parse Action

```python
    # Parse response
    action = parse_white_agent_response(response_text)
    thought = action.get("thought", "")
    tool = action.get("tool", "finish")
    params = action.get("params", {})

    # Check if finished
    if tool == "finish":
        success = True
        break
```

**`parse_white_agent_response()`** (`src/shared/response_parser.py`):
- Tries multiple formats:
  1. JSON with `<json>...</json>` tags
  2. Structured text: `THOUGHT: ... ACTION: ... PARAMS: ...`
  3. Fallback: treat entire response as "finish" action
- Returns: `{"thought": str, "tool": str, "params": dict}`

#### 8e. Execute Action in Browser

```python
    # Execute action
    result = await browser_agent.execute_action(tool, **params)

    if not result.get("success", False):
        # Log error but continue (give agent another chance)
        logger.warning(f"Action failed: {result.get('error')}")
```

**`BrowserAgent.execute_action()`** (`src/shared/browser_agent.py:151-260`):
```python
async def execute_action(self, tool_name: str, **kwargs) -> Dict[str, Any]:
    if tool_name == "click":
        return await self._action_click(kwargs.get("selector", ""))
    elif tool_name == "type":
        return await self._action_type(
            kwargs.get("selector", ""),
            kwargs.get("text", "")
        )
    elif tool_name == "select":
        return await self._action_select(
            kwargs.get("selector", ""),
            kwargs.get("value", "")
        )

async def _action_click(self, selector: str):
    await self.page.click(selector, timeout=5000)
    await self.page.wait_for_load_state("load", timeout=5000)
    # Record action in history
    self.action_history.append(f"{selector} -> CLICK")
    # Take screenshot
    await self.take_screenshot(f"step_{self.step_count:03d}")
    return {"success": True}
```

**Pattern**: After each action, the system:
1. Waits for page load
2. Records action in history (Mind2Web format)
3. Takes full-page screenshot
4. Returns success/failure

#### 8f. Loop Until Complete

The loop continues until:
- White agent returns `tool="finish"` (success)
- Max steps reached (failure)
- Error occurs (failure)

#### 8g. Save Session and Return Result

```python
    # Save browser session
    browser_agent.save_session(
        task_id=task_id,
        task_description=task_description,
        final_response=f"Task {'completed' if success else 'failed'} after {step_count} steps",
        thoughts=thoughts
    )

    # Create evaluation result
    result = EvalResult(
        winner="white_agent" if success else "none",
        detail={
            "task_id": task_id,
            "success": success,
            "steps_taken": step_count,
            "action_history": browser_agent.get_action_history(),
            "screenshots": browser_agent.get_screenshots(),
            ...
        }
    )

    # Return as A2A artifact
    await updater.add_artifact(
        parts=[Part(root=TextPart(text=result.model_dump_json(indent=2)))],
        name="EvaluationResult"
    )
```

**Session saved to**: `.output/browser_eval_{task_id}/{task_id}.json`

### Step 9: Client Receives Result

**File**: `src/agentbeats/client_cli.py:35-94`

```python
# Client receives streaming events
async for event in client.send_message(outbound_msg):
    match event:
        case Message() as msg:
            print(merge_parts(msg.parts))
        case (task, update):
            # Print status updates
            # Print artifacts (EvalResult)
```

**What happens**:
1. Client receives streaming events from green agent
2. Status updates are printed as they arrive
3. Final artifact (EvalResult) is printed as JSON

### Step 10: Shutdown

**File**: `src/agentbeats/run_scenario.py:283-304`

```python
finally:
    print("\nShutting down...")
    for p in procs:
        if p.poll() is None:  # Still running
            os.killpg(p.pid, signal.SIGTERM)  # Graceful shutdown
    time.sleep(1)
    for p in procs:
        if p.poll() is None:
            os.killpg(p.pid, signal.SIGKILL)  # Force kill

    # Close log files
    for log_file in log_files:
        log_file.close()
```

**What happens**:
1. Send SIGTERM to all processes (graceful shutdown)
2. Wait 1 second
3. Send SIGKILL to any remaining processes (force kill)
4. Close all log file handles

---

## 6. File-by-File Code Explanation

### Orchestration Layer

#### `src/agentbeats/run_scenario.py`

**Purpose**: Main entry point that orchestrates the entire evaluation

**Lines**: 308 total

**Key Classes**:
- `TeeFile` (33-59): Multiplexes writes to multiple file handles
  ```python
  class TeeFile:
      def __init__(self, *files):
          self.files = files

      def write(self, data):
          for f in self.files:
              f.write(data)
              f.flush()
  ```
  **Why**: Allows simultaneous writing to log file AND stdout, ensuring logs are captured even when displayed in terminal.

**Key Functions**:
- `parse_toml(scenario_path)` (111-148): Parses scenario.toml into config dict
  - Extracts host/port from endpoints
  - Builds participants list
  - Returns structured config

- `wait_for_agents(cfg, timeout=30)` (62-108): Polls agent health
  - Fetches agent card from each endpoint
  - Retries until all agents respond or timeout
  - Uses `A2ACardResolver` for A2A-compliant health checks

- `main()` (151-308): **Main orchestration logic**
  1. Parse CLI args and scenario.toml
  2. Create timestamped log files
  3. Spawn white agent subprocess(es)
  4. Spawn green agent subprocess
  5. Wait for agents to be ready
  6. Spawn client_cli subprocess (unless `--serve-only`)
  7. Wait for client to finish
  8. Shutdown all processes gracefully

**Integration Points**:
- Spawns: `browser_judge.py`, `white_agent.py`, `client_cli.py` as subprocesses
- Uses: `subprocess.Popen` for process management
- Uses: `A2ACardResolver` for health checking

**Design Pattern**: **Process Manager** - Manages lifecycle of multiple subprocesses with proper logging and cleanup

---

#### `src/agentbeats/client_cli.py`

**Purpose**: Sends evaluation request to green agent and prints results

**Lines**: 106 total

**Key Functions**:
- `parse_toml(scenario_path)` (15-34): Extracts participants and config from scenario.toml
  - Returns `(participants_dict, config_dict)`
  - Participants: `{"role": "endpoint"}`
  - Config: Task-specific settings

- `event_consumer()` (37-52): Async callback for streaming events
  - Prints each event as it arrives
  - Handles both Message and TaskStatusUpdate events

- `main()` (55-106): **Main client logic**
  1. Parse scenario.toml
  2. Build `EvalRequest` from participants + config
  3. Send JSON to green agent via `send_message()`
  4. Print streaming events
  5. Print final response

**Code Flow**:
```python
async def main():
    participants, config = parse_toml(sys.argv[1])

    # Build evaluation request
    req = EvalRequest(participants=participants, config=config)

    # Send to green agent
    outputs = await send_message(
        message=req.model_dump_json(),
        base_url=green_endpoint,
        consumer=event_consumer
    )

    print(outputs["response"])
```

**Integration Points**:
- Uses: `send_message()` from `client.py` (A2A communication)
- Sends to: Green agent at endpoint from scenario.toml
- Returns: Prints result to stdout

---

#### `scenarios/web_browser/scenario.toml`

**Purpose**: Configuration file for the browser evaluation scenario

**Lines**: 16 total

**Structure**:
```toml
[green_agent]
endpoint = "http://127.0.0.1:9009"
cmd = "python scenarios/web_browser/browser_judge.py --host 127.0.0.1 --port 9009"

[[participants]]
role = "white_agent"
endpoint = "http://127.0.0.1:9019"
cmd = "python scenarios/web_browser/white_agent.py --host 127.0.0.1 --port 9019"

[config]
task_id = "20a460a8fe1971b84411c5b1e6ac4186"
website = "https://www.stubhub.com/"
task = "Show theatre events for Las Vegas and select one."
max_steps = 10
level = "easy"
```

**Sections**:
1. **`[green_agent]`**: Green agent configuration
   - `endpoint`: URL where green agent will be accessible
   - `cmd`: Shell command to start green agent

2. **`[[participants]]`**: White agent(s) configuration (can have multiple)
   - `role`: Identifier for this participant
   - `endpoint`: URL where white agent will be accessible
   - `cmd`: Shell command to start white agent

3. **`[config]`**: Task-specific configuration (passed to green agent)
   - `task_id`: Unique task identifier
   - `website`: Target website URL
   - `task`: Natural language task description
   - `max_steps`: Maximum number of actions allowed
   - `level`: Difficulty level

**How It Flows**:
1. `run_scenario.py` parses this file
2. Spawns processes from `cmd` fields
3. Waits for `endpoint` URLs to be healthy
4. Passes `config` section to green agent in EvalRequest

---

### A2A Communication Layer

#### `src/agentbeats/client.py`

**Purpose**: A2A protocol client for sending messages to agents

**Lines**: 81 total

**Key Functions**:
- `create_message(role, text, context_id)` (12-21): Creates A2A Message
  ```python
  def create_message(role=Role.user, text: str, context_id=None):
      return Message(
          kind="message",
          role=role,
          parts=[Part(TextPart(kind="text", text=text))],
          message_id=uuid4().hex,  # Unique ID
          context_id=context_id    # For multi-turn
      )
  ```

- `merge_parts(parts)` (24-31): Extracts text from A2A message parts
  - Handles both `TextPart` and `DataPart`
  - Joins multiple parts with newlines

- `send_message(message, base_url, context_id, streaming, consumer)` (34-80): **Core A2A client**
  ```python
  async def send_message(message: str, base_url: str, context_id=None):
      # Fetch agent card
      resolver = A2ACardResolver(httpx_client=client, base_url=base_url)
      agent_card = await resolver.get_agent_card()

      # Create A2A client
      config = ClientConfig(httpx_client=client, streaming=streaming)
      factory = ClientFactory(config)
      client = factory.create(agent_card)

      # Add event consumer if provided
      if consumer:
          await client.add_event_consumer(consumer)

      # Send message
      outbound_msg = create_message(text=message, context_id=context_id)
      async for event in client.send_message(outbound_msg):
          last_event = event

      # Extract response from last event
      match last_event:
          case Message() as msg:
              return {"context_id": msg.context_id, "response": merge_parts(msg.parts)}
          case (task, update):
              # Task with artifacts
              return {"context_id": task.context_id, "status": task.status.state.value, ...}
  ```

**Code Flow**:
1. Resolve agent card (A2A service discovery)
2. Create A2A client from card
3. Send message with optional context_id
4. Stream events (or get single response)
5. Return response + context_id

**Integration Points**:
- Uses: `a2a.client` library (A2A protocol implementation)
- Used by: `tool_provider.py`, `client_cli.py`

**Design Pattern**: **Client Factory** - Uses factory pattern to create clients from agent cards

---

#### `src/agentbeats/tool_provider.py`

**Purpose**: Wrapper for agent-to-agent communication with context management

**Lines**: 34 total

**Key Classes**:
```python
class ToolProvider:
    def __init__(self):
        self._context_ids = {}  # {url: context_id}

    async def talk_to_agent(self, message: str, url: str, new_conversation=False):
        outputs = await send_message(
            message=message,
            base_url=url,
            context_id=None if new_conversation else self._context_ids.get(url, None)
        )
        # Save context for next message
        self._context_ids[url] = outputs.get("context_id", None)
        return outputs["response"]

    def reset(self):
        self._context_ids = {}
```

**Purpose**:
- **Simplifies** agent communication (vs. using `send_message()` directly)
- **Manages context** automatically for multi-turn conversations
- **Maps URL to context_id** so callers don't need to track it

**Usage Pattern**:
```python
tool_provider = ToolProvider()

# First message (new_conversation=True)
response1 = await tool_provider.talk_to_agent(
    message="HTML: ...",
    url="http://localhost:9019",
    new_conversation=True
)

# Second message (reuses context_id automatically)
response2 = await tool_provider.talk_to_agent(
    message="HTML: ...",
    url="http://localhost:9019",
    new_conversation=False
)

# Reset when done
tool_provider.reset()
```

**Integration Points**:
- Uses: `send_message()` from `client.py`
- Used by: `browser_judge.py` (green agent)

**Design Pattern**: **Facade** - Provides simplified interface over complex A2A client

---

#### `src/agentbeats/models.py`

**Purpose**: Data structures for evaluation requests and results

**Lines**: 14 total

**Key Classes**:
```python
class EvalRequest(BaseModel):
    participants: Dict[str, str]  # {role: endpoint}
    config: Dict[str, Any]        # Task-specific config

class EvalResult(BaseModel):
    winner: str                   # "white_agent", "none", etc.
    detail: Dict[str, Any]        # Detailed results
```

**Example**:
```python
request = EvalRequest(
    participants={"white_agent": "http://127.0.0.1:9019"},
    config={
        "task_id": "...",
        "website": "https://...",
        "task": "...",
        "max_steps": 10
    }
)

result = EvalResult(
    winner="white_agent",
    detail={
        "success": True,
        "steps_taken": 5,
        "action_history": [...],
        "screenshots": [...]
    }
)
```

**Integration Points**:
- Used by: `green_executor.py`, `browser_judge.py`, `client_cli.py`
- Serialized as: JSON for A2A messages

---

### Agent Framework Layer

#### `src/agentbeats/green_executor.py`

**Purpose**: Adapter that bridges A2A protocol and custom green agent logic

**Lines**: 77 total

**Key Classes**:

**1. GreenAgent (Abstract Base Class)** (15-23):
```python
class GreenAgent:
    @abstractmethod
    async def run_eval(self, request: EvalRequest, updater: TaskUpdater):
        """Run the evaluation logic"""
        pass

    @abstractmethod
    def validate_request(self, request: EvalRequest) -> tuple[bool, str]:
        """Validate the evaluation request"""
        pass
```

**Why**: Defines contract for green agents. Any green agent must implement these two methods.

**2. GreenExecutor (AgentExecutor Adapter)** (26-76):
```python
class GreenExecutor(AgentExecutor):
    def __init__(self, green_agent: GreenAgent):
        self.agent = green_agent

    async def execute(self, context: RequestContext, event_queue: EventQueue):
        # 1. Parse incoming message as EvalRequest
        request_text = context.get_user_input()
        req = EvalRequest.model_validate_json(request_text)

        # 2. Validate request
        ok, msg = self.agent.validate_request(req)
        if not ok:
            raise ServerError(error=InvalidParamsError(message=msg))

        # 3. Create A2A task
        task = new_task(msg)
        await event_queue.enqueue_event(task)

        # 4. Create TaskUpdater for status updates
        updater = TaskUpdater(event_queue, task.id, task.context_id)
        await updater.update_status(TaskState.working, ...)

        # 5. Run custom green agent logic
        try:
            await self.agent.run_eval(req, updater)
            await updater.complete()
        except Exception as e:
            await updater.failed(...)
```

**Code Flow**:
```
A2A Message (JSON)
  ↓
GreenExecutor.execute()
  ↓ parse & validate
EvalRequest (Pydantic model)
  ↓ create task & updater
GreenAgent.run_eval(req, updater)
  ↓ custom logic runs
TaskUpdater.add_artifact(result)
  ↓
A2A Task with artifacts
```

**Integration Points**:
- Extends: `AgentExecutor` from `a2a.server`
- Used by: `browser_judge.py` wraps `BrowserJudge` in `GreenExecutor`
- Provides: `TaskUpdater` to green agent for status updates

**Design Pattern**: **Adapter** - Adapts custom green agent to A2A protocol interface

---

#### `scenarios/web_browser/browser_judge.py`

**Purpose**: Green agent that evaluates web automation agents using Playwright

**Lines**: 436 total

**Key Classes**:

**BrowserJudge** (48-320): Main green agent implementation

**Initialization** (62-67):
```python
def __init__(self):
    self._required_roles = ["white_agent"]
    self._required_config_keys = ["task_id", "website", "task", "max_steps"]
    self._tool_provider = ToolProvider()
```

**Key Methods**:

1. **`validate_request(request)`** (69-90): Validates EvalRequest
   ```python
   def validate_request(self, request: EvalRequest):
       # Check for required roles
       missing_roles = set(self._required_roles) - set(request.participants.keys())
       if missing_roles:
           return False, f"Missing roles: {missing_roles}"

       # Check for required config
       missing_config = set(self._required_config_keys) - set(request.config.keys())
       if missing_config:
           return False, f"Missing config: {missing_config}"

       return True, "ok"
   ```

2. **`run_eval(req, updater)`** (92-320): **Main evaluation logic**

   **Phase 1: Setup** (102-132)
   ```python
   # Extract config
   white_agent_url = req.participants["white_agent"]
   task_id = req.config["task_id"]
   website = req.config["website"]
   task_description = req.config["task"]
   max_steps = req.config["max_steps"]

   # Initialize browser
   browser_agent = BrowserAgent(headless=False, output_dir=f".output/browser_eval_{task_id}")
   await browser_agent.start(website)
   ```

   **Phase 2: Evaluation Loop** (166-247)
   ```python
   for step in range(max_steps):
       # Get cleaned HTML
       html = await browser_agent.get_html(cleaned=True, format="html")
       html_truncated = html[:20000]  # LLM context limit

       # Send to white agent
       response_text = await self._tool_provider.talk_to_agent(
           message=initial_prompt + html_truncated,
           url=white_agent_url,
           new_conversation=(step == 0)
       )

       # Parse action
       action = parse_white_agent_response(response_text)
       tool = action.get("tool", "finish")
       params = action.get("params", {})

       # Check if finished
       if tool == "finish":
           success = True
           break

       # Execute action
       result = await browser_agent.execute_action(tool, **params)

       # Continue even if action fails (give agent another chance)
   ```

   **Phase 3: Save & Return Results** (252-293)
   ```python
   # Save browser session
   browser_agent.save_session(task_id, task_description, ...)

   # Create result
   result = EvalResult(
       winner="white_agent" if success else "none",
       detail={...}
   )

   # Add as A2A artifact
   await updater.add_artifact(
       parts=[Part(root=TextPart(text=result.model_dump_json()))],
       name="EvaluationResult"
   )
   ```

   **Phase 4: Cleanup** (315-319)
   ```python
   finally:
       await browser_agent.stop()
       self._tool_provider.reset()
   ```

**Key Functions**:

**`browser_judge_agent_card(agent_name, card_url)`** (322-365): Creates A2A agent card
```python
def browser_judge_agent_card(agent_name: str, card_url: str):
    skill = AgentSkill(
        id="evaluate_web_agent",
        name="Evaluates web automation agents",
        description="...",
        examples=[
            # JSON example of EvalRequest
        ]
    )

    agent_card = AgentCard(
        name=agent_name,
        url=card_url,
        capabilities=AgentCapabilities(streaming=True),
        skills=[skill]
    )
    return agent_card
```

**`main()`** (368-431): Entry point
```python
async def main():
    # Parse CLI args
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9009)
    args = parser.parse_args()

    # Create agent and executor
    agent = BrowserJudge()
    executor = GreenExecutor(agent)
    agent_card = browser_judge_agent_card("BrowserJudge", f"http://{args.host}:{args.port}")

    # Create A2A server
    request_handler = DefaultRequestHandler(agent_executor=executor, task_store=InMemoryTaskStore())
    server = A2AStarletteApplication(agent_card=agent_card, http_handler=request_handler)

    # Start uvicorn
    uvicorn.run(server.build(), host=args.host, port=args.port)
```

**Integration Points**:
- Extends: `GreenAgent` abstract base class
- Uses: `BrowserAgent` for Playwright automation
- Uses: `ToolProvider` for white agent communication
- Uses: `parse_white_agent_response()` for action parsing
- Runs: Uvicorn server with A2A protocol

**Design Pattern**:
- **Template Method**: `GreenAgent` defines template, `BrowserJudge` implements specifics
- **Coordinator**: Orchestrates browser, white agent, and evaluation logic

---

#### `scenarios/web_browser/white_agent.py`

**Purpose**: White agent that receives HTML and returns navigation actions

**Lines**: 100 total

**Key Functions**:

**`browser_agent_card(host, port, card_url)`** (22-33): Creates agent card
```python
def browser_agent_card(host, port, card_url=None):
    return AgentCard(
        name="browser_agent",
        description="A web browser navigation agent...",
        url=card_url or f"http://{host}:{port}/",
        capabilities=AgentCapabilities(streaming=True)
    )
```

**`main()`** (36-99): Entry point
```python
def main():
    # Create Google ADK agent with Gemini
    root_agent = Agent(
        name="browser_agent",
        model="gemini-2.0-flash-exp",  # Fast Gemini model
        instruction="""You are a helpful web automation agent.

        Always respond in JSON format:
        {
            "thought": "your reasoning",
            "tool": "tool_name",
            "params": {"param": "value"}
        }

        Available tools:
        - click, type, select, scroll, wait, finish
        """
    )

    # Convert to A2A and run
    agent_card = browser_agent_card(args.host, args.port)
    a2a_app = to_a2a(root_agent, agent_card=agent_card)
    uvicorn.run(a2a_app, host=args.host, port=args.port)
```

**How It Works**:
1. Uses Google ADK (Agent Development Kit)
2. Configures Gemini 2.0 Flash model
3. Provides instruction prompt with tool descriptions
4. `to_a2a()` converts ADK agent to A2A-compliant server
5. Runs uvicorn server

**Integration Points**:
- Uses: Google ADK (`google.adk.agents.Agent`)
- Uses: `google.adk.a2a.utils.agent_to_a2a.to_a2a()` (ADK → A2A adapter)
- Communicates with: Green agent via A2A protocol

**Design Pattern**: **Adapter** - Google ADK agent adapted to A2A protocol

---

### Browser Automation Layer

#### `src/shared/browser_agent.py`

**Purpose**: Playwright wrapper for browser automation

**Lines**: 526 total

**Key Classes**:

**BrowserAgent** (16-526):

**Initialization** (26-41):
```python
def __init__(self, headless=False, output_dir="./output"):
    self.headless = headless
    self.output_dir = Path(output_dir)
    self.output_dir.mkdir(exist_ok=True, parents=True)

    # State
    self.browser: Optional[Browser] = None
    self.page: Optional[Page] = None
    self.action_history: List[str] = []
    self.screenshots: List[str] = []
    self.step_count: int = 0

    self.html_cleaner = HTMLCleaner()
```

**Key Methods**:

1. **`start(url)`** (114-143): Launch browser and navigate
   ```python
   async def start(self, url: str):
       # Launch Playwright
       playwright = await async_playwright().start()
       self.browser = await normal_launch_async(playwright, headless=self.headless)

       # Create context with viewport 1280x720
       context = await normal_new_context_async(self.browser)
       context.on("page", self.page_on_open_handler)

       # Create page and navigate
       await context.new_page()
       await self.page.goto(url, wait_until="load")

       # Take initial screenshot
       await self.take_screenshot("initial")
   ```

2. **`execute_action(tool_name, **kwargs)`** (151-260): Execute browser action
   ```python
   async def execute_action(self, tool_name: str, **kwargs):
       self.step_count += 1

       if tool_name == "click":
           return await self._action_click(kwargs.get("selector"))
       elif tool_name == "type":
           return await self._action_type(kwargs.get("selector"), kwargs.get("text"))
       elif tool_name == "select":
           return await self._action_select(kwargs.get("selector"), kwargs.get("value"))
       else:
           return {"success": False, "error": f"Unknown tool: {tool_name}"}
   ```

3. **`_action_click(selector)`** (262-303): Click action
   ```python
   async def _action_click(self, selector: str):
       try:
           await self.page.click(selector, timeout=5000)
           await self.page.wait_for_load_state("load", timeout=5000)

           # Record action
           self.action_history.append(f"{selector} -> CLICK")

           # Take screenshot
           screenshot_path = await self.take_screenshot(f"step_{self.step_count:03d}")

           return {"success": True, "screenshot": screenshot_path}
       except Exception as e:
           return {"success": False, "error": str(e)}
   ```

4. **`get_html(cleaned, format)`** (382-411): Get page HTML
   ```python
   async def get_html(self, cleaned=True, format="html"):
       raw_html = await self.page.content()

       if cleaned:
           if format == "html":
               return self.html_cleaner.clean(raw_html)
           elif format == "text_tree":
               return self.html_cleaner.clean_to_text_tree(raw_html)

       return raw_html
   ```

5. **`take_screenshot(name)`** (413-428): Capture screenshot
   ```python
   async def take_screenshot(self, name: str):
       path = self.output_dir / f"{name}.png"
       await self.page.screenshot(path=str(path), full_page=True)
       self.screenshots.append(str(path))
       return str(path)
   ```

6. **`save_session(...)`** (430-483): Save session to JSON
   ```python
   def save_session(self, task_id, task_description, final_response, thoughts):
       session_data = {
           "task_id": task_id,
           "task": task_description,
           "final_result_response": final_response,
           "action_history": self.action_history,
           "thoughts": thoughts,
           "screenshots": self.screenshots,
           "metadata": {
               "timestamp": datetime.now().isoformat(),
               "total_steps": self.step_count,
               "final_url": self.page.url
           }
       }

       output_file = self.output_dir / f"{task_id}.json"
       with open(output_file, "w") as f:
           json.dump(session_data, f, indent=2)
   ```

**Event Handlers** (96-111):
```python
async def page_on_navigation_handler(self, frame):
    print("page_on_navigation_handler")

async def page_on_close_handler(self, page):
    logger.info("page_on_close_handler")

async def page_on_crash_handler(self, page):
    logger.info(f"Page crashed: {page.url}")
    await page.reload()  # Try to recover
```

**Integration Points**:
- Uses: Playwright async API
- Uses: `browser_helper.py` for initialization
- Uses: `html_cleaner.py` for HTML preprocessing
- Used by: `browser_judge.py`

**Design Pattern**: **Facade** - Simplifies Playwright's complex API

---

#### `src/shared/html_cleaner.py`

**Purpose**: Clean HTML to reduce size for LLM processing

**Lines**: 423 total

**Key Classes**:

**HTMLCleaner** (11-423):

**Configuration** (14-67):
```python
REMOVE_TAGS = {"script", "style", "svg", "iframe", ...}  # Remove completely
UNWRAP_TAGS = {"font", "center", "marquee", "blink"}    # Remove tag, keep content
INTERACTIVE_TAGS = {"a", "button", "input", "select", ...}  # Always keep
KEEP_ATTRIBUTES = {"id", "name", "type", "value", "href", ...}  # Useful attributes
```

**Initialization** (69-88):
```python
def __init__(self, remove_hidden=True, remove_comments=True, max_text_length=200):
    self.remove_hidden = remove_hidden
    self.remove_comments = remove_comments
    self.max_text_length = max_text_length
```

**Key Methods**:

1. **`clean(html)`** (90-123): Full HTML cleaning pipeline
   ```python
   def clean(self, html: str) -> str:
       soup = BeautifulSoup(html, "html.parser")

       # Multi-stage cleaning
       self._remove_tags(soup, self.REMOVE_TAGS)
       self._remove_comments(soup)
       self._remove_hidden_elements(soup)
       self._clean_attributes(soup)
       self._simplify_text(soup)
       self._remove_empty_elements(soup)

       return str(soup)
   ```

2. **`_remove_tags(soup, tags)`** (125-131): Remove specified tags
   ```python
   def _remove_tags(self, soup, tags):
       for tag_name in tags:
           for tag in soup.find_all(tag_name):
               tag.decompose()  # Remove completely
   ```

3. **`_remove_hidden_elements(soup)`** (150-176): Remove hidden elements
   ```python
   def _remove_hidden_elements(self, soup):
       for element in soup.find_all():
           style = element.get("style", "")

           # Check for display:none, visibility:hidden
           if "display:none" in style or "visibility:hidden" in style:
               element.decompose()

           # Check for hidden attribute
           if element.get("hidden") is not None:
               element.decompose()

           # Check for aria-hidden
           if element.get("aria-hidden") == "true":
               element.decompose()
   ```

4. **`_clean_attributes(soup)`** (178-191): Remove unnecessary attributes
   ```python
   def _clean_attributes(self, soup):
       for element in soup.find_all():
           # Keep only useful attributes
           attrs_to_keep = {
               k: v for k, v in element.attrs.items()
               if k in self.KEEP_ATTRIBUTES
           }
           element.attrs = attrs_to_keep
   ```

5. **`_simplify_text(soup)`** (193-213): Truncate long text
   ```python
   def _simplify_text(self, soup):
       for element in soup.find_all(string=True):
           text = element.strip()
           if len(text) > self.max_text_length:
               element.replace_with(text[:self.max_text_length] + "...")
   ```

6. **`_remove_empty_elements(soup)`** (215-236): Remove empty elements
   ```python
   def _remove_empty_elements(self, soup):
       for element in soup.find_all():
           # Don't remove interactive elements
           if element.name in self.INTERACTIVE_TAGS:
               continue

           # Remove if no text and no interactive children
           if not element.get_text(strip=True) and not element.find(self.INTERACTIVE_TAGS):
               element.decompose()
   ```

**Why This Matters**:
- Raw HTML can be 500KB-5MB
- LLMs have context limits (e.g., 128K tokens ≈ 500KB)
- Cleaned HTML typically 10-50KB
- Keeps all actionable elements (buttons, links, inputs)
- Removes visual noise (SVG, scripts, styles)

**Integration Points**:
- Uses: BeautifulSoup4 for parsing
- Used by: `BrowserAgent.get_html()`

**Design Pattern**: **Pipeline** - Multi-stage cleaning process

---

#### `src/shared/response_parser.py`

**Purpose**: Parse LLM responses into structured action format

**Lines**: 78 total

**Key Functions**:

**`parse_white_agent_response(response_text)`** (17-78): Parse action from text
```python
def parse_white_agent_response(response_text: str) -> dict:
    """
    Parse white agent response into action format.

    Supports multiple formats:
    1. JSON: <json>{"thought": "...", "tool": "...", "params": {...}}</json>
    2. Structured text: THOUGHT: ... ACTION: ... PARAMS: ...
    3. Fallback: treat as finish action

    Returns: {"thought": str, "tool": str, "params": dict}
    """

    # Try JSON format
    json_match = re.search(r'<json>(.*?)</json>', response_text, re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group(1))
            return {
                "thought": data.get("thought", ""),
                "tool": data.get("tool", "finish"),
                "params": data.get("params", {})
            }
        except json.JSONDecodeError:
            pass

    # Try structured text format
    thought_match = re.search(r'THOUGHT:\s*(.+?)(?=ACTION:|TOOL:|$)', response_text, re.IGNORECASE | re.DOTALL)
    action_match = re.search(r'(?:ACTION|TOOL):\s*(\w+)', response_text, re.IGNORECASE)
    params_match = re.search(r'PARAMS:\s*(.+)', response_text, re.IGNORECASE | re.DOTALL)

    if action_match:
        return {
            "thought": thought_match.group(1).strip() if thought_match else "",
            "tool": action_match.group(1).strip().lower(),
            "params": json.loads(params_match.group(1)) if params_match else {}
        }

    # Fallback: treat as finish
    return {
        "thought": response_text[:200],
        "tool": "finish",
        "params": {}
    }
```

**Why Multiple Formats?**:
- LLMs don't always follow format instructions perfectly
- JSON format is ideal but not always produced
- Structured text is a fallback
- Graceful degradation ensures system keeps running

**Integration Points**:
- Used by: `browser_judge.py` to parse white agent responses

---

#### `src/shared/browser_helper.py`

**Purpose**: Playwright initialization utilities

**Lines**: 46 total

**Key Functions**:

**`normal_launch_async(playwright, headless, args)`** (10-22): Launch browser
```python
async def normal_launch_async(playwright, headless=False, args=None):
    return await playwright.chromium.launch(
        headless=headless,
        args=args or []
    )
```

**`normal_new_context_async(browser, user_agent, record_video)`** (25-46): Create context
```python
async def normal_new_context_async(browser, user_agent=None, record_video=False):
    context_args = {
        "user_agent": user_agent or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/109.0.0.0",
        "viewport": {"width": 1280, "height": 720},
        "accept_downloads": True
    }

    if record_video:
        context_args["record_video_dir"] = "videos/"

    return await browser.new_context(**context_args)
```

**Integration Points**:
- Used by: `BrowserAgent.start()`

---

### Utilities

#### `src/utils/common_utils.py`

**Purpose**: General utility functions

**Lines**: 16 total

**Key Functions**:

**`build_url(host, port, secure)`** (4-10): Construct URL
```python
def build_url(host: str, port: int, secure: bool = False) -> str:
    protocol = "https" if secure else "http"
    return f"{protocol}://{host}:{port}"
```

**`parse_tags(text, tag_name)`** (13-16): Extract XML-style tags
```python
def parse_tags(text: str, tag_name: str) -> str:
    pattern = f"<{tag_name}>(.*?)</{tag_name}>"
    match = re.search(pattern, text, re.DOTALL)
    return match.group(1) if match else ""
```

---

#### `src/agentbeats/cloudflare.py`

**Purpose**: Create Cloudflare Quick Tunnels for public agent access

**Lines**: 42 total

**Key Functions**:

**`quick_tunnel(local_url)`** (10-42): Async context manager for tunnel
```python
@contextlib.asynccontextmanager
async def quick_tunnel(local_url: str):
    """
    Create a Cloudflare Quick Tunnel to expose local agent publicly.

    Usage:
        async with quick_tunnel("http://localhost:9009") as public_url:
            # Agent is now accessible at public_url
    """
    proc = subprocess.Popen(
        ["cloudflared", "tunnel", "--url", local_url],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT
    )

    # Wait for tunnel URL to appear in output
    public_url = None
    while proc.poll() is None:
        line = proc.stdout.readline().decode()
        if "trycloudflare.com" in line:
            public_url = extract_url(line)
            break

    try:
        yield public_url
    finally:
        proc.kill()
```

**Use Case**: Optional feature for exposing agents outside localhost (e.g., for remote evaluation)

---

## 7. Key Concepts Deep Dive

### Browser Automation Workflow

#### Complete Lifecycle

```
start() → action loop → stop()
  ↓          ↓            ↓
Launch    Execute     Close
browser   actions     browser
```

**1. Start Phase**:
```python
await browser_agent.start("https://example.com")
```
- Launches Playwright chromium browser
- Creates context with 1280x720 viewport
- Sets user agent (Windows Chrome)
- Navigates to URL with `wait_until="load"`
- Registers event handlers (navigation, crash, close)
- Takes initial screenshot

**2. Action Loop Phase**:
```python
for step in range(max_steps):
    result = await browser_agent.execute_action("click", selector="#button")
```
- Gets HTML from current page
- Sends to white agent
- Receives action
- Executes action (click, type, select)
- Waits for page load
- Records action in history
- Takes screenshot

**3. Stop Phase**:
```python
await browser_agent.stop()
```
- Closes browser
- Saves session data
- Cleans up resources

#### State Management Across Steps

**BrowserAgent maintains**:
```python
self.browser: Browser       # Playwright browser instance
self.page: Page            # Current page
self.action_history: []    # List of actions taken
self.screenshots: []       # Paths to screenshots
self.step_count: int       # Current step number
```

**Why state matters**:
- Action history is saved to JSON
- Screenshots are saved with step numbers
- Step count appears in logs and results

#### Playwright Best Practices Implemented

1. **Wait for load state**: After each action
   ```python
   await self.page.click(selector)
   await self.page.wait_for_load_state("load", timeout=5000)
   ```

2. **Event handlers**: For navigation, crash, close
   ```python
   page.on("crash", self.page_on_crash_handler)  # Auto-reload on crash
   ```

3. **Timeouts**: Every action has timeout
   ```python
   await self.page.click(selector, timeout=5000)
   ```

4. **Full-page screenshots**: Capture entire page
   ```python
   await self.page.screenshot(path=path, full_page=True)
   ```

5. **Error handling**: Try-except around all actions
   ```python
   try:
       await self.page.click(selector)
       return {"success": True}
   except Exception as e:
       return {"success": False, "error": str(e)}
   ```

#### Why Certain Waits and Timeouts Are Used

**`wait_for_load_state("load")`**: Waits for page to finish loading
- **When**: After click, type actions
- **Why**: Ensures page updates before next action
- **Timeout**: 5000ms (5 seconds)

**`timeout=5000` on actions**: Max time for action to complete
- **Why**: Pages can be slow; prevents hanging forever
- **Trade-off**: Too short = false negatives; too long = slow evaluation

**No wait on `select`**: Dropdown selections are instant
- **Why**: No page navigation, just JS event

---

### HTML Cleaning Strategy

#### The Problem

**Raw HTML is too large for LLM context**:
- Typical website: 500KB - 5MB of HTML
- Most LLMs: 128K token limit (≈ 500KB)
- GPT-4: 32K tokens (≈ 128KB)
- Gemini 2.0 Flash: 1M tokens (≈ 4MB) but expensive to process

**Most HTML is noise**:
- `<script>` tags with JavaScript
- `<style>` tags with CSS
- `<svg>` graphics (thousands of `<path>` elements)
- Hidden elements (`display:none`)
- Metadata (`<meta>`, `<link>`)

**What we need**:
- Actionable elements: buttons, links, inputs
- Structure: headings, labels, text
- Identifiers: id, class, name, data-* attributes

#### Multi-Stage Cleaning Pipeline

```
Raw HTML (5MB)
  ↓ 1. Remove tags (script, style, svg, iframe)
HTML (2MB)
  ↓ 2. Remove comments
HTML (1.8MB)
  ↓ 3. Remove hidden elements (display:none, visibility:hidden)
HTML (1MB)
  ↓ 4. Clean attributes (keep only id, name, class, href, type, value, etc.)
HTML (500KB)
  ↓ 5. Simplify text (truncate to 200 chars per element)
HTML (200KB)
  ↓ 6. Remove empty elements (except interactive)
Cleaned HTML (50KB)
```

#### What Gets Removed and Why

**Removed completely**:
- `<script>`: JavaScript code (not useful for navigation)
- `<style>`: CSS rules (visual styling, not structure)
- `<svg>`, `<path>`: Graphics (huge, not actionable)
- `<iframe>`: Embedded content (separate context)
- `<video>`, `<audio>`: Media elements (not navigable)
- `<meta>`, `<link>`: Metadata (not visible)

**Unwrapped (tag removed, content kept)**:
- `<font>`, `<center>`: Deprecated styling tags
- `<marquee>`, `<blink>`: Obsolete animation tags

**Always kept**:
- `<a>`: Links (clickable)
- `<button>`: Buttons (clickable)
- `<input>`: Form inputs (typeable)
- `<select>`: Dropdowns (selectable)
- `<form>`: Form containers (structure)

**Attributes kept**:
- Identifiers: `id`, `name`, `data-testid`
- Form data: `type`, `value`, `placeholder`
- Navigation: `href`, `src`
- Accessibility: `aria-label`, `role`, `alt`, `title`
- Styling (useful): `class` (for selectors)

**Attributes removed**:
- Event handlers: `onclick`, `onload`
- Styling: `style` (except when checking for hidden)
- Tracking: Most `data-*` except `data-testid`, `data-id`

#### Trade-offs: Completeness vs. Token Efficiency

**Aggressive cleaning** (current approach):
- ✅ Fits in LLM context
- ✅ Faster LLM processing
- ✅ Cheaper API calls
- ❌ May lose some navigation cues
- ❌ May remove elements agent needs

**Minimal cleaning** (keep more):
- ✅ More complete information
- ✅ Better for complex pages
- ❌ May exceed context limit
- ❌ Slower LLM processing
- ❌ More expensive

**Current balance**:
- 20000 char limit in browser_judge (line 179-182)
- 200 char per text element in HTMLCleaner
- Removes noise, keeps structure
- **Result**: 95%+ of pages fit in context with all actionable elements preserved

#### Example

**Before cleaning** (1.2MB):
```html
<html>
<head>
  <script>var analytics = {track: function() {...}};</script>
  <style>.button { background: blue; border-radius: 4px; }</style>
  <meta name="description" content="...">
  <link rel="stylesheet" href="styles.css">
</head>
<body>
  <svg width="100" height="100">
    <path d="M10 10 L90 90 L10 90 Z" fill="red"/>
  </svg>
  <div style="display:none" class="hidden-promo">...</div>
  <button id="submit-btn" onclick="submitForm()" class="btn btn-primary" data-analytics="submit-click">
    Submit Form
  </button>
</body>
</html>
```

**After cleaning** (0.3KB):
```html
<html>
<body>
  <button id="submit-btn" class="btn btn-primary">
    Submit Form
  </button>
</body>
</html>
```

**Reduction**: 1.2MB → 0.3KB (99.98% smaller!)
**Preserved**: Button is still clickable with same selector

---

### Action Execution Pattern

#### From LLM Text → Playwright Command

```
White Agent LLM Response (text)
  ↓
parse_white_agent_response()
  ↓
{"thought": "...", "tool": "click", "params": {"selector": "#button"}}
  ↓
BrowserAgent.execute_action("click", selector="#button")
  ↓
_action_click("#button")
  ↓
await page.click("#button")
  ↓
await page.wait_for_load_state("load")
  ↓
action_history.append("#button -> CLICK")
  ↓
await take_screenshot("step_001")
  ↓
return {"success": True, "screenshot": "..."}
```

#### Error Handling and Graceful Degradation

**Philosophy**: Keep evaluation running even when actions fail

**Example**:
```python
# In browser_judge.py (line 229-246)
try:
    result = await browser_agent.execute_action(tool, **params)

    if not result.get("success", False):
        error_message = result.get("error", "Unknown error")
        logger.warning(f"Action execution failed: {error_message}")
        # Continue to next step rather than breaking - give agent another chance
    else:
        logger.info("Action executed successfully")
except Exception as e:
    error_message = f"Exception: {str(e)}"
    logger.error(error_message)
    # Continue to next step
```

**Why continue on failure?**:
1. **Selector might be wrong**: LLM might pick better selector next time
2. **Page might load slowly**: Next action might succeed
3. **Element might appear**: Dynamic content loads over time
4. **Partial success**: Agent made progress even if one step failed

**Alternative**: Could break on first error, but this:
- ❌ Penalizes agents too harshly for minor mistakes
- ❌ Doesn't reflect real-world usage (humans retry)
- ❌ Wastes evaluation time (could have succeeded later)

#### Why Actions "Succeed" Even When They "Fail"

**Example scenario**:
```python
# Step 1: Click search button
result = await browser_agent.execute_action("click", selector="#search-btn")
# Returns: {"success": True}

# Step 2: Type in search box
result = await browser_agent.execute_action("type", selector="#search-input", text="Las Vegas")
# Returns: {"success": False, "error": "Timeout: Selector not found"}

# Step 3: Click search again (different selector)
result = await browser_agent.execute_action("click", selector="button[type='submit']")
# Returns: {"success": True}
```

**What happened**:
- Step 1: Clicked button, page navigated
- Step 2: Selector was wrong (maybe search box has different ID)
- Step 3: LLM tried different selector, succeeded!

**If we stopped at step 2**:
- Agent would be marked as failure
- But agent was learning and adapting

#### Screenshot Timing Strategy

**When screenshots are taken**:
1. **Initial**: Right after page loads (`browser_agent.start()`)
2. **After successful action**: After click/type/select succeeds
3. **NOT after failed actions**: Avoid duplicates, page didn't change

**Why this timing?**:
- ✅ Captures page state after each change
- ✅ Useful for debugging (see what agent saw)
- ✅ Useful for dataset creation (action → result pairs)
- ❌ Takes disk space (20-50KB per screenshot)

**Screenshot format**:
```
.output/browser_eval_{task_id}/
  initial.png           # Before any actions
  step_001.png          # After first successful action
  step_002.png          # After second successful action
  ...
```

**Full-page screenshots**:
```python
await self.page.screenshot(path=path, full_page=True)
```
- Captures entire page, not just viewport
- Important because actionable elements might be off-screen

---

### Multi-Turn Conversations

#### Context ID Management

**What is context_id?**:
- A unique identifier that links messages in a conversation
- Part of A2A Message structure
- Allows agent to remember previous messages

**How it works**:

**First message** (new conversation):
```python
message = Message(
    role=Role.user,
    parts=[Part(TextPart(text="HTML: ... Task: ..."))],
    message_id="msg-001",
    context_id=None  # No context = new conversation
)
```

**Agent response**:
```python
response = Message(
    role=Role.agent,
    parts=[Part(TextPart(text='{"tool": "click", ...}'))],
    message_id="msg-002",
    context_id="ctx-abc123"  # Agent assigns context ID
)
```

**Second message** (continuation):
```python
message = Message(
    role=Role.user,
    parts=[Part(TextPart(text="HTML: ... What next?"))],
    message_id="msg-003",
    context_id="ctx-abc123"  # Same context = continuation
)
```

#### How Green Agent Maintains Conversation with White Agent

**ToolProvider manages context** (`src/agentbeats/tool_provider.py`):
```python
class ToolProvider:
    def __init__(self):
        self._context_ids = {}  # {url: context_id}

    async def talk_to_agent(self, message, url, new_conversation=False):
        # Get context_id for this agent URL
        context_id = None if new_conversation else self._context_ids.get(url)

        # Send message
        outputs = await send_message(message, url, context_id=context_id)

        # Save context_id for next message
        self._context_ids[url] = outputs.get("context_id")

        return outputs["response"]
```

**In browser_judge.py** (line 195-199):
```python
response_text = await self._tool_provider.talk_to_agent(
    message=message,
    url=white_agent_url,
    new_conversation=(step == 0)  # New conversation on first step
)
```

**Step-by-step flow**:

**Step 0** (new conversation):
```
Green: "HTML: <html>..., Task: Show theatre events"
  context_id=None
White: {"tool": "click", "selector": "#theatre"}
  context_id="ctx-001"
[ToolProvider saves: {"http://localhost:9019": "ctx-001"}]
```

**Step 1** (continuation):
```
Green: "HTML: <html>..., What next?"
  context_id="ctx-001" (from ToolProvider)
White: {"tool": "type", "selector": "#location", "text": "Las Vegas"}
  context_id="ctx-001"
```

**Step 2** (continuation):
```
Green: "HTML: <html>..., What next?"
  context_id="ctx-001"
White: {"tool": "click", "selector": "#search-btn"}
  context_id="ctx-001"
```

#### When Contexts Are Preserved vs. Reset

**Preserved**:
- ✅ During evaluation loop (steps 0 to max_steps)
- ✅ Same white agent URL
- ✅ Same task

**Reset**:
- ❌ After evaluation completes (`tool_provider.reset()`)
- ❌ New evaluation request
- ❌ Different white agent URL

**Why preserve context?**:
- White agent can remember previous actions
- White agent can reason about what didn't work
- White agent can avoid repeating mistakes

**Example with context**:
```
Step 1: Green: "HTML: ... Click the search button"
        White: {"tool": "click", "selector": "#search"}
        Result: Failed (selector not found)

Step 2: Green: "HTML: ... Try again"
        White: {"tool": "click", "selector": "button[aria-label='Search']"}
        Result: Success!
```

White agent remembered it tried `#search` and failed, so it tried a different selector.

**Example without context** (would be):
```
Step 1: Green: "HTML: ... Click the search button"
        White: {"tool": "click", "selector": "#search"}
        Result: Failed

Step 2: Green: "HTML: ... Try again"
        White: {"tool": "click", "selector": "#search"}  # Tries same thing!
        Result: Failed again
```

---

### Agent Communication Patterns

#### Request-Response Flow

**Basic pattern**:
```
Client → Request → Green Agent → Process → Response → Client
```

**With white agent**:
```
Client → EvalRequest → Green Agent
                          ↓
                  HTML → White Agent → Action
                          ↓
                  Execute Action
                          ↓
                  EvalResult → Client
```

#### Streaming Events

**Why streaming?**: Long-running evaluations need progress updates

**A2A supports streaming** via Server-Sent Events (SSE):
```python
async for event in client.send_message(message):
    match event:
        case Message():
            # Intermediate message
        case (Task, TaskStatusUpdate):
            # Status update
```

**In WABE** (`browser_judge.py`):
```python
# Green agent sends status updates during evaluation
await updater.update_status(
    TaskState.working,
    new_agent_text_message(f"Executing step {step_count}/{max_steps}")
)
```

**Client receives** (`client_cli.py`):
```python
# Client prints updates as they arrive
async def event_consumer(event):
    print(f"Event: {event}")
```

**Timeline**:
```
0s:   Client sends EvalRequest
1s:   Green agent: "Starting evaluation"
2s:   Green agent: "Executing step 1/10"
5s:   Green agent: "Executing step 2/10"
8s:   Green agent: "Executing step 3/10"
...
30s:  Green agent: "Evaluation complete" + EvalResult artifact
```

#### Task Status Updates

**Task states**:
```python
TaskState.pending    # Task received, not started
TaskState.working    # Task in progress
TaskState.completed  # Task finished successfully
TaskState.failed     # Task failed with error
```

**Status update pattern**:
```python
# 1. Create task
updater = TaskUpdater(event_queue, task.id, task.context_id)

# 2. Update status during work
await updater.update_status(
    TaskState.working,
    new_agent_text_message("Progress message")
)

# 3. Complete with success
await updater.complete()

# OR: Complete with failure
await updater.failed(new_agent_text_message("Error message"))
```

#### Artifact Creation

**What is an artifact?**: Final result/output of a task

**In WABE** (`browser_judge.py` line 282-285):
```python
await updater.add_artifact(
    parts=[Part(root=TextPart(text=result.model_dump_json(indent=2)))],
    name="EvaluationResult"
)
```

**Artifact structure**:
```python
Artifact(
    name="EvaluationResult",
    parts=[
        Part(root=TextPart(text='{"winner": "white_agent", "detail": {...}}'))
    ]
)
```

**Why artifacts?**:
- Separate result from progress messages
- Can have multiple artifacts per task
- Structured output (JSON)
- Client can parse and process

---

### Error Handling Philosophy

#### Fail Gracefully, Continue Evaluation

**Traditional approach** (strict):
```python
if not action_succeeded:
    raise Exception("Action failed!")
    # Evaluation stops, agent marked as failure
```

**WABE approach** (graceful):
```python
if not action_succeeded:
    logger.warning(f"Action failed: {error}")
    # Continue to next step, give agent another chance
```

**Why graceful?**:
1. **Agents learn**: Next action might be better
2. **Real-world usage**: Humans retry when actions fail
3. **Partial credit**: Agent might succeed on subsequent attempts
4. **More data**: Get full action sequence, not just first error

**Example**:
```
Step 1: Click "#submit" → Failed (selector not found)
Step 2: Click "button[type='submit']" → Success!
Step 3: Type "#email", "test@example.com" → Success!
Step 4: Finish → Success!

Result: 3/4 actions succeeded, task completed
```

With strict approach, would have stopped at step 1 with 0% success.

#### Logging Strategy

**Three levels of logging**:

1. **INFO**: Normal operation
   ```python
   logger.info("Starting browser evaluation")
   logger.info("Executing action: click")
   logger.info("Evaluation complete. Success: True")
   ```

2. **WARNING**: Recoverable errors
   ```python
   logger.warning("Action execution failed: Selector not found")
   logger.warning("Failed to communicate with white agent, retrying...")
   ```

3. **ERROR**: Serious errors (but evaluation continues)
   ```python
   logger.error("Failed to parse white agent response", exc_info=True)
   logger.error("Unexpected error during evaluation", exc_info=True)
   ```

**Logging locations**:
- **Green agent**: `.logs/{timestamp}_green.log`
- **White agent**: `.logs/{timestamp}_white.log`
- **Client**: `.logs/{timestamp}_app.log`

**What to log**:
- ✅ Start/stop of major operations
- ✅ Actions executed and results
- ✅ Agent communication (sent/received)
- ✅ Errors with full traceback (`exc_info=True`)
- ❌ HTML content (too large)
- ❌ Screenshot data (binary)

#### When to Abort vs. Continue

**Continue when**:
- ✅ Action fails (selector not found, timeout)
- ✅ White agent returns invalid action format
- ✅ Screenshot fails to save
- ✅ HTML cleaning produces empty result

**Abort when**:
- ❌ Browser crashes and can't reload
- ❌ White agent URL is unreachable
- ❌ Max steps reached (time limit)
- ❌ White agent returns "finish" (task complete)

**Example decisions**:

**Scenario 1**: Selector not found
```python
# Continue - agent can try different selector
if not result.get("success"):
    logger.warning("Action failed, continuing to next step")
    continue  # Not break!
```

**Scenario 2**: White agent unreachable
```python
# Abort - can't proceed without white agent
try:
    response = await talk_to_agent(...)
except Exception as e:
    logger.error(f"Failed to communicate: {e}")
    break  # Can't continue without actions
```

**Scenario 3**: Max steps reached
```python
# Abort - time limit exceeded
if step_count >= max_steps:
    logger.info("Reached max steps")
    success = False
    break
```

---

## 8. Configuration & Customization

### Modifying scenario.toml

**Location**: `scenarios/web_browser/scenario.toml`

**Change ports**:
```toml
[green_agent]
endpoint = "http://127.0.0.1:9009"  # Change port here
cmd = "python scenarios/web_browser/browser_judge.py --host 127.0.0.1 --port 9009"  # And here

[[participants]]
endpoint = "http://127.0.0.1:9019"  # Change port here
cmd = "python scenarios/web_browser/white_agent.py --host 127.0.0.1 --port 9019"  # And here
```

**Change task**:
```toml
[config]
task_id = "my_custom_task"
website = "https://amazon.com/"
task = "Search for 'laptop' and add first result to cart"
max_steps = 15  # Allow more steps for complex task
level = "medium"
```

**Add second white agent** (for comparison):
```toml
[[participants]]
role = "white_agent_gpt4"
endpoint = "http://127.0.0.1:9020"
cmd = "python scenarios/web_browser/white_agent_gpt4.py --host 127.0.0.1 --port 9020"
```

### Adding New Tasks

**Option 1**: Modify scenario.toml directly (quick)
```toml
[config]
task_id = "20a460a8fe1971b84411c5b1e6ac4186"
website = "https://www.stubhub.com/"
task = "Show theatre events for Las Vegas and select one."
```

**Option 2**: Create tasks.json (reusable)
```json
{
  "tasks": [
    {
      "task_id": "task_001",
      "website": "https://example.com",
      "task": "Description",
      "level": "easy"
    }
  ]
}
```

Then modify `client_cli.py` to load from JSON.

### Adjusting Agent Behavior

#### Green Agent (browser_judge.py)

**Change HTML truncation limit**:
```python
# Line 179-182
html_truncated = html[:20000]  # Change 20000 to different value
```

**Change evaluation criteria**:
```python
# Line 224-227
if tool == "finish":
    # Add custom logic: check if task actually completed
    if self._verify_task_completion():
        success = True
        break
```

**Change prompt to white agent**:
```python
# Line 135-164
initial_prompt = f"""You are a web automation agent...
TASK: {task_description}

# Add custom instructions here
IMPORTANT: Always check for CAPTCHA...
"""
```

#### White Agent (white_agent.py)

**Change LLM model**:
```python
# Line 55
model="gemini-2.0-flash-exp"  # Change to "gemini-1.5-pro", etc.
```

**Change instruction prompt**:
```python
# Line 57-85
instruction="""You are a helpful web automation agent.

# Customize instructions
Your goal is to complete tasks with minimal actions...
"""
```

**Add custom tools**:
```python
# In instruction
- scroll: Scroll the page (params: {"direction": "up|down", "amount": 500})
- wait: Wait for element (params: {"selector": "css_selector", "timeout": 5000})
```

### Environment Variables

**Required**:
```bash
# .env file
GOOGLE_API_KEY=your_api_key_here
GOOGLE_GENAI_USE_VERTEXAI=FALSE
```

**Optional**:
```bash
# Custom log directory
LOG_DIR=.logs

# Playwright settings
PLAYWRIGHT_BROWSERS_PATH=/path/to/browsers

# Debug mode
DEBUG=true
```

**Loading in code**:
```python
from dotenv import load_dotenv
load_dotenv()

# Then use os.getenv()
api_key = os.getenv("GOOGLE_API_KEY")
```

---

## 9. Output & Logging

### Understanding Log Files

**Location**: `.logs/` directory

**Three log files per run**:
```
.logs/
├── 2025-11-19_20-23-13_green.log   # Green agent (browser_judge.py)
├── 2025-11-19_20-23-27_white.log   # White agent (white_agent.py)
└── 2025-11-19_20-23-38_app.log     # Client (client_cli.py)
```

**Log format**:
```
2025-11-19 20:23:38,225 - green_agent.default_agent - INFO - STARTING TASK EVALUATION
[timestamp]                [logger name]             [level] [message]
```

**Reading green agent logs**:
```bash
tail -f .logs/2025-11-19_20-23-13_green.log

# Look for:
# - "Starting browser evaluation" (evaluation started)
# - "Executing step N/M" (progress)
# - "Sending message to white agent" (communication)
# - "Received response from white agent" (action received)
# - "Executing action: tool_name" (action execution)
# - "Action executed successfully" / "Action execution failed" (result)
# - "Evaluation complete. Success: true/false" (final result)
```

**Reading white agent logs**:
```bash
tail -f .logs/2025-11-19_20-23-27_white.log

# Look for:
# - "Uvicorn running on http://localhost:9019" (agent started)
# - "TASK: description" (task received from green agent)
# - Gemini API logs (model inference)
```

**Reading app logs**:
```bash
tail -f .logs/2025-11-19_20-23-38_app.log

# Look for:
# - Evaluation request sent
# - Streaming events received
# - Final result
```

### Output Directory Structure

**Location**: `.output/browser_eval_{task_id}/`

**Contents**:
```
.output/browser_eval_20a460a8fe1971b84411c5b1e6ac4186/
├── 20a460a8fe1971b84411c5b1e6ac4186.json  # Session data (JSON)
├── initial.png                            # Screenshot: initial page
├── step_001.png                           # Screenshot: after step 1
├── step_002.png                           # Screenshot: after step 2
└── step_003.png                           # Screenshot: after step 3
```

### Session JSON Format

**File**: `.output/browser_eval_{task_id}/{task_id}.json`

**Structure**:
```json
{
  "task_id": "20a460a8fe1971b84411c5b1e6ac4186",
  "task": "Show theatre events for Las Vegas and select one.",
  "final_result_response": "Task completed after 3 steps",

  "action_history": [
    "#location-input -> TYPE: Las Vegas",
    "#search-button -> CLICK",
    ".event-card:first-child -> CLICK"
  ],

  "thoughts": [
    "Step 1: First, I need to enter the location...",
    "Step 2: Now I'll click the search button...",
    "Step 3: I'll select the first event..."
  ],

  "screenshots": [
    ".output/browser_eval_.../initial.png",
    ".output/browser_eval_.../step_001.png",
    ".output/browser_eval_.../step_002.png",
    ".output/browser_eval_.../step_003.png"
  ],

  "metadata": {
    "timestamp": "2025-11-23T10:56:15.079038",
    "total_steps": 3,
    "final_url": "https://www.stubhub.com/theatre-tickets/las-vegas-nv-104/events/"
  }
}
```

**Fields**:
- **task_id**: Unique task identifier
- **task**: Natural language task description
- **final_result_response**: Summary of result
- **action_history**: List of actions in Mind2Web format
- **thoughts**: LLM reasoning for each step
- **screenshots**: Paths to screenshot files
- **metadata**: Timestamp, step count, final URL

### Debugging Tips

**Problem**: Agent not finding elements

**Solution 1**: Check screenshots
```bash
open .output/browser_eval_*/step_*.png
# Look at what the agent saw
```

**Solution 2**: Check HTML
```python
# Add to browser_judge.py after line 177
with open(self.output_dir / "page_html.html", "w") as f:
    f.write(html)
# Then open page_html.html in browser to see cleaned HTML
```

**Problem**: Actions failing

**Solution**: Check green agent logs for errors
```bash
grep "Action execution failed" .logs/*_green.log
# See which actions failed and why
```

**Problem**: White agent not responding

**Solution 1**: Check white agent logs
```bash
tail -f .logs/*_white.log
# See if white agent is receiving messages
```

**Solution 2**: Check agent card
```bash
curl http://localhost:9019/.well-known/agent-card.json
# Should return agent card JSON
```

**Problem**: Evaluation hangs

**Solution**: Check for timeouts in logs
```bash
grep "timeout" .logs/*_green.log -i
# Look for Playwright timeout errors
```

**Problem**: Max steps reached without completion

**Solution**: Increase max_steps in scenario.toml
```toml
[config]
max_steps = 20  # Increase from 10
```

---

## 10. Common Patterns & Best Practices

### A2A Message Patterns

**Pattern 1: Simple message**
```python
message = create_message(
    role=Role.user,
    text="Hello, agent!",
    context_id=None  # New conversation
)
```

**Pattern 2: Continuation**
```python
message = create_message(
    role=Role.user,
    text="What's next?",
    context_id=previous_context_id  # Continue conversation
)
```

**Pattern 3: Structured request**
```python
request = EvalRequest(
    participants={"white_agent": "http://localhost:9019"},
    config={"task": "...", "max_steps": 10}
)
message = create_message(
    role=Role.user,
    text=request.model_dump_json(),  # Serialize as JSON
    context_id=None
)
```

**Pattern 4: Streaming events**
```python
async for event in client.send_message(message):
    match event:
        case Message() as msg:
            print(f"Message: {merge_parts(msg.parts)}")
        case (task, update):
            print(f"Status: {task.status.state.value}")
```

### Async/Await Patterns

**Pattern 1: Sequential operations**
```python
# When order matters
await browser.start(url)
await browser.execute_action("click", selector="#button")
await browser.stop()
```

**Pattern 2: Parallel operations**
```python
# When operations are independent
import asyncio
results = await asyncio.gather(
    fetch_url(url1),
    fetch_url(url2),
    fetch_url(url3)
)
```

**Pattern 3: Context managers**
```python
async with browser_agent.start(url):
    # Browser is running
    await browser_agent.execute_action(...)
# Browser automatically stopped
```

**Pattern 4: Error handling**
```python
try:
    result = await browser.execute_action(...)
except asyncio.TimeoutError:
    logger.warning("Action timed out")
except Exception as e:
    logger.error(f"Unexpected error: {e}", exc_info=True)
```

### Context Management

**Pattern 1: Manual context tracking**
```python
context_id = None

# First message
outputs = await send_message(message1, url, context_id=None)
context_id = outputs["context_id"]

# Second message
outputs = await send_message(message2, url, context_id=context_id)
```

**Pattern 2: Automatic context (ToolProvider)**
```python
tool_provider = ToolProvider()

# First message (new_conversation=True)
response1 = await tool_provider.talk_to_agent(message1, url, new_conversation=True)

# Second message (context preserved automatically)
response2 = await tool_provider.talk_to_agent(message2, url, new_conversation=False)
```

**Pattern 3: Context reset**
```python
tool_provider.reset()  # Clear all context_ids
# Next message will start new conversation
```

### Error Handling

**Pattern 1: Try-except with logging**
```python
try:
    result = await operation()
except SpecificError as e:
    logger.warning(f"Expected error: {e}")
    # Handle gracefully
except Exception as e:
    logger.error(f"Unexpected error: {e}", exc_info=True)
    # Log full traceback
```

**Pattern 2: Retry logic**
```python
max_retries = 3
for attempt in range(max_retries):
    try:
        result = await operation()
        break  # Success!
    except RetryableError:
        if attempt < max_retries - 1:
            await asyncio.sleep(1)
        else:
            raise  # Final attempt failed
```

**Pattern 3: Fallback values**
```python
try:
    value = parse_complex(data)
except ParseError:
    value = default_value  # Use fallback
```

**Pattern 4: Context manager cleanup**
```python
try:
    await browser.start(url)
    # ... do work ...
finally:
    await browser.stop()  # Always cleanup
```

---

## 11. Development Workflow

### Running the System

**Basic run**:
```bash
uv run agentbeats-run scenarios/web_browser/scenario.toml
```

**With logs visible**:
```bash
uv run agentbeats-run scenarios/web_browser/scenario.toml --show-logs
```

**Serve only (no evaluation)**:
```bash
uv run agentbeats-run scenarios/web_browser/scenario.toml --serve-only
# Agents stay running, you can test manually
```

### Reading Logs Effectively

**Real-time monitoring**:
```bash
# Terminal 1: Run evaluation
uv run agentbeats-run scenario.toml --show-logs

# Terminal 2: Watch specific log
tail -f .logs/*_green.log | grep -E "STEP|Action|Error"

# Terminal 3: Watch screenshots being created
watch -n 1 'ls -lht .output/browser_eval_*/step_*.png | head -5'
```

**Post-run analysis**:
```bash
# Count successful actions
grep "Action executed successfully" .logs/*_green.log | wc -l

# Count failed actions
grep "Action execution failed" .logs/*_green.log | wc -l

# See all actions taken
grep "Executing action:" .logs/*_green.log

# See LLM thoughts
jq '.thoughts[]' .output/browser_eval_*/*.json
```

### Troubleshooting Common Issues

**Issue 1: Port already in use**
```bash
# Find process using port
lsof -ti:9009 | xargs kill -9
lsof -ti:9019 | xargs kill -9

# Or change port in scenario.toml
```

**Issue 2: Google API quota exceeded**
```
Error: 429 RESOURCE_EXHAUSTED
```
**Solution**: Wait for quota reset or upgrade to paid tier

**Issue 3: Playwright browser not installed**
```bash
playwright install
```

**Issue 4: Environment variables not loaded**
```bash
# Check .env exists
ls -la .env

# Check contents
cat .env

# Reload environment
source .env  # If using shell
```

**Issue 5: Browser crashes**
**Solution**: Check logs for crash reason, increase timeouts

**Issue 6: Selector not found**
**Solution**:
1. Look at screenshots to see page state
2. Try different selector (CSS vs XPath)
3. Wait for dynamic content to load

### Testing Changes

**Test browser automation**:
```python
# Create test script: test_browser.py
import asyncio
from src.shared.browser_agent import BrowserAgent

async def test():
    agent = BrowserAgent(headless=False, output_dir=".output/test")
    await agent.start("https://example.com")
    result = await agent.execute_action("click", selector="a")
    print(result)
    await agent.stop()

asyncio.run(test())
```

**Test HTML cleaning**:
```python
# Create test script: test_cleaner.py
from src.shared.html_cleaner import HTMLCleaner

html = """<html>
<head><script>alert('test')</script></head>
<body><button id="submit">Submit</button></body>
</html>"""

cleaner = HTMLCleaner()
cleaned = cleaner.clean(html)
print(cleaned)
```

**Test white agent**:
```bash
# Start white agent
python scenarios/web_browser/white_agent.py --port 9019

# In another terminal, send test request
curl -X POST http://localhost:9019/messages \
  -H "Content-Type: application/json" \
  -d '{"message": "HTML: <button id=\"submit\">Submit</button>\nTask: Click submit"}'
```

**Test green agent**:
```bash
# Start green agent
python scenarios/web_browser/browser_judge.py --port 9009

# Send evaluation request via client_cli
python -m agentbeats.client_cli scenarios/web_browser/scenario.toml
```

---

## 12. Appendix

### Glossary of Terms

**A2A (Agent-to-Agent)**: Open protocol for agent communication via JSON-RPC over HTTP

**AgentBeats**: Framework for agentified evaluation using green and white agents

**Agent Card**: JSON document describing agent capabilities, published at `/.well-known/agent-card.json`

**Artifact**: Result/output of a task, attached to A2A Task

**Browser Agent**: Component that wraps Playwright for browser automation

**Context ID**: Identifier linking messages in a multi-turn conversation

**EvalRequest**: Pydantic model containing participants and config for evaluation

**EvalResult**: Pydantic model containing evaluation results (winner, details)

**Green Agent**: Evaluator/judge agent that orchestrates evaluation

**Green Executor**: Adapter that bridges GreenAgent and A2A AgentExecutor interface

**Headless**: Browser mode without visible window (faster, for CI/CD)

**LLM**: Large Language Model (e.g., Gemini, GPT-4)

**Playwright**: Browser automation library (like Selenium but modern)

**Task State**: Status of A2A task (pending, working, completed, failed)

**TaskUpdater**: Object for sending status updates and artifacts during A2A task

**TeeFile**: Utility that writes to multiple file handles simultaneously

**ToolProvider**: Wrapper for agent communication with automatic context management

**White Agent**: Participant agent being evaluated by green agent

### External Resources and Documentation Links

**A2A Protocol**:
- [Official Specification](https://a2a-protocol.org/latest/specification/)
- [GitHub Repository](https://github.com/a2aproject/A2A)
- [Google Blog Post](https://developers.googleblog.com/en/a2a-a-new-era-of-agent-interoperability/)
- [IBM Explainer](https://www.ibm.com/think/topics/agent2agent-protocol)

**AgentBeats Framework**:
- [Documentation](https://docs.agentbeats.org/)
- [Google ADK](https://google.github.io/adk-docs/)
- [Evaluation Guide](https://google.github.io/adk-docs/evaluate/)

**Related Technologies**:
- [Playwright Documentation](https://playwright.dev/)
- [Google Gemini](https://ai.google.dev/)
- [BeautifulSoup4 Documentation](https://www.crummy.com/software/BeautifulSoup/bs4/doc/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [Uvicorn Documentation](https://www.uvicorn.org/)

### Architecture Decisions

**Why A2A protocol?**
- **Standardization**: Common protocol for all agents
- **Interoperability**: Mix agents from different frameworks
- **Streaming**: Support for long-running tasks
- **Context**: Multi-turn conversations built-in

**Why AgentBeats framework?**
- **Reusability**: Green agents can be shared and reused
- **Standardization**: Common evaluation interface
- **Flexibility**: Easy to add new benchmarks

**Why Playwright over Selenium?**
- **Modern API**: Async/await support
- **Better waits**: Auto-waits for elements
- **Faster**: More efficient browser control
- **Better debugging**: Screenshots, videos, traces

**Why clean HTML aggressively?**
- **Context limits**: LLMs have token limits
- **Cost**: Larger context = more expensive API calls
- **Speed**: Smaller context = faster inference
- **Focus**: Remove noise, keep actionable elements

**Why continue on action failures?**
- **Robustness**: Agents can recover from mistakes
- **Real-world**: Humans retry when actions fail
- **Better data**: Full action sequences for analysis

**Why Gemini 2.0 Flash?**
- **Speed**: Fast inference (~1-2s per action)
- **Cost**: Cheaper than GPT-4
- **Quality**: Good enough for navigation tasks
- **Context**: 1M token context window

**Why separate green and white agents?**
- **Modularity**: Easy to swap white agents
- **Comparison**: Run same evaluation with different agents
- **Standardization**: Green agent defines evaluation logic once

---

## Conclusion

You now have a comprehensive understanding of WABE:

✅ **What it is**: Browser automation benchmark for evaluating AI agents
✅ **How it works**: Green agent orchestrates browser, white agent decides actions
✅ **A2A protocol**: Standardized agent communication
✅ **AgentBeats framework**: Agentified evaluation pattern
✅ **File structure**: What each file does and why it exists
✅ **Execution flow**: Step-by-step from start to finish
✅ **Key concepts**: HTML cleaning, action execution, context management, error handling
✅ **Configuration**: How to modify and customize
✅ **Debugging**: How to read logs and troubleshoot issues

**Next steps**:
1. Run an evaluation: `uv run agentbeats-run scenarios/web_browser/scenario.toml`
2. Examine the outputs: Look at `.output/` and `.logs/`
3. Modify a task: Change `scenario.toml` and run again
4. Explore the code: Read files in order of execution flow
5. Create a custom green agent: Extend `GreenAgent` for a new benchmark

**Questions?** Check the external resources or explore the code with this document as your guide!

---

*Document generated for WABE project. Last updated: 2025-11-24*

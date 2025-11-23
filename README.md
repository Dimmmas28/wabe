# WABE - Web Agent Browser Evaluation

A browser automation benchmark using the AgentBeats framework. WABE evaluates AI agents on their ability to navigate websites and complete realistic web tasks using the A2A (Agent-to-Agent) protocol.

## Quick Start

### Prerequisites

- Python 3.10+
- [uv](https://github.com/astral-sh/uv) package manager
- Google API key (for Gemini model)
- Playwright browsers

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd wabe

# Install dependencies
uv sync

# Install Playwright browsers
playwright install

# Set up environment variables
cp .env.example .env
# Edit .env and add your GOOGLE_API_KEY
```

### Running WABE

Run the complete evaluation with a single command:

```bash
uv run agentbeats-run scenarios/web_browser/scenario.toml
```

That's it! The system will:
1. Start the green agent (browser judge) on port 9009
2. Start the white agent (web automation) on port 9019
3. Execute the browser automation task
4. Save results to `.output/` directory
5. Shut down cleanly when complete

## Architecture

WABE follows the [AgentBeats](https://github.com/google/agentbeats) evaluation framework pattern:

### Components

**Green Agent (Judge)** - `scenarios/web_browser/browser_judge.py`
- Orchestrates browser automation evaluation
- Manages Playwright browser instance
- Sends HTML + task description to white agent via A2A protocol
- Executes actions received from white agent
- Evaluates task completion
- **Reuses existing code**: `BrowserAgent` (529 lines) from `src/green_agent/task_execution/`

**White Agent (Participant)** - `scenarios/web_browser/white_agent.py`
- Receives HTML and task via A2A protocol
- Uses Google Gemini 2.0 Flash (`gemini-2.0-flash-exp`) to reason about actions
- Returns structured JSON actions (click, type, select, scroll, wait, finish)
- Built with Google ADK (Agent Development Kit)

**A2A Protocol**
- Standardized agent-to-agent communication
- JSON-based message passing
- Agent cards for capability discovery
- Task and artifact management

### Data Flow

```
1. AgentBeats loads scenario.toml configuration
2. Green agent opens browser → navigates to target website
3. Green agent extracts HTML → sends to white agent
4. White agent (LLM) analyzes HTML + task → returns action
5. Green agent executes action in browser
6. Repeat steps 3-5 until task complete or max steps reached
7. Green agent evaluates result → creates artifact
```

## Environment Setup

### Required Environment Variables

Create a `.env` file (copy from `.env.example`):

```bash
# Use standard Google AI API (not Vertex AI)
GOOGLE_GENAI_USE_VERTEXAI=FALSE

# Your Google API key for Gemini models
# Get one at: https://aistudio.google.com/app/apikey
GOOGLE_API_KEY=your_api_key_here
```

### Optional Configuration

Edit `scenarios/web_browser/scenario.toml` to customize:

```toml
[config]
task_id = "20a460a8fe1971b84411c5b1e6ac4186"  # Task from data/tasks.json
max_steps = 10                                 # Maximum interaction steps
```

## Output Structure

After running an evaluation, outputs are saved to:

```
.output/
└── browser_eval_{task_id}/
    ├── {task_id}.json      # Evaluation results and metadata
    └── initial.png         # Screenshot(s) of browser state
```

### Example Output JSON

```json
{
  "task_id": "20a460a8fe1971b84411c5b1e6ac4186",
  "task": "Show theatre events for Las Vegas and select one.",
  "final_result_response": "Task failed after 1 steps",
  "action_history": [],
  "thoughts": [],
  "screenshots": [".output/browser_eval_.../initial.png"],
  "metadata": {
    "timestamp": "2025-11-23T10:56:15.079038",
    "total_steps": 0,
    "final_url": "https://www.stubhub.com/"
  }
}
```

## Reading Logs

### Real-time Logs

Use the `--show-logs` flag to see live output:

```bash
uv run agentbeats-run scenarios/web_browser/scenario.toml --show-logs
```

This displays real-time logs from both agents as they communicate.

### Log Files

Logs are saved to `.logs/` directory with timestamps:

```
.logs/
├── 2025-11-19_20-23-13_green.log   # Green agent logs
├── 2025-11-19_20-23-27_white.log   # White agent logs
└── 2025-11-19_20-23-38_app.log     # Main application logs
```

### Example Log Output

**Green Agent Log** (`.logs/YYYY-MM-DD_HH-MM-SS_green.log`):
```
2025-11-19 20:23:38,225 - green_agent.default_agent - INFO - ============================================================
2025-11-19 20:23:38,225 - green_agent.default_agent - INFO - STARTING TASK EVALUATION
2025-11-19 20:23:38,225 - green_agent.default_agent - INFO - Task ID: 20a460a8fe1971b84411c5b1e6ac4186
2025-11-19 20:23:38,225 - green_agent.default_agent - INFO - Task: Show theatre events for Las Vegas and select one.
2025-11-19 20:23:38,225 - green_agent.default_agent - INFO - Website: https://www.stubhub.com/
2025-11-19 20:24:02,602 - green_agent.default_agent - INFO - STEP 1/10
2025-11-19 20:24:03,500 - green_agent.utils.a2a_client - INFO - → GREEN AGENT: Sending to white agent...
```

**White Agent Log** (`.logs/YYYY-MM-DD_HH-MM-SS_white.log`):
```
2025-11-19 20:23:27,312 - uvicorn.error - INFO - Application startup complete.
2025-11-19 20:23:27,314 - uvicorn.error - INFO - Uvicorn running on http://localhost:9002 (Press CTRL+C to quit)
2025-11-19 20:24:03,561 - white_agent.a2a.agent_executor - INFO - TASK: Show theatre events for Las Vegas and select one.
```

### What to Look For

- **Green agent startup**: `Uvicorn running on http://localhost:9009`
- **White agent startup**: `Uvicorn running on http://localhost:9019`
- **Task submission**: `STARTING TASK EVALUATION`
- **A2A communication**: `→ GREEN AGENT: Sending to white agent...`
- **Actions executed**: Look for tool calls (click, type, etc.)
- **Errors**: Search for `ERROR` or `RESOURCE_EXHAUSTED` (API quota)

## Troubleshooting

### API Quota Errors (429 RESOURCE_EXHAUSTED)

**Problem**: Google Gemini free tier has rate limits

```
google.api_core.exceptions.ResourceExhausted: 429 RESOURCE_EXHAUSTED
```

**Solutions**:
1. Wait for quota reset (usually hourly)
2. Use a paid Google Cloud API key
3. Reduce `max_steps` in scenario.toml
4. Switch to a different model (edit `white_agent.py`)

### Port Already in Use

**Problem**: Ports 9009 or 9019 already occupied

**Solutions**:
```bash
# Find and kill process using port
lsof -ti:9009 | xargs kill -9
lsof -ti:9019 | xargs kill -9

# Or edit scenario.toml to use different ports
```

### Playwright Browser Not Installed

**Problem**: `playwright._impl._errors.Error: Executable doesn't exist`

**Solution**:
```bash
playwright install
```

### Missing Google API Key

**Problem**: `GOOGLE_API_KEY environment variable not set`

**Solution**:
1. Get API key: https://aistudio.google.com/app/apikey
2. Add to `.env` file: `GOOGLE_API_KEY=your_key_here`

## Testing Flags

### Show Logs

Display real-time logs from both agents:

```bash
uv run agentbeats-run scenarios/web_browser/scenario.toml --show-logs
```

### Serve Only

Start agents without running evaluation (useful for debugging):

```bash
uv run agentbeats-run scenarios/web_browser/scenario.toml --serve-only
```

Agents will stay running on their ports. Test manually:

```bash
# Check green agent card
curl http://localhost:9009/.well-known/agent-card.json

# Check white agent card
curl http://localhost:9019/.well-known/agent-card.json
```

Press Ctrl+C to stop.

## Project Structure

```
wabe/
├── scenarios/
│   └── web_browser/           # Browser automation scenario
│       ├── scenario.toml      # AgentBeats configuration
│       ├── browser_judge.py   # Green agent (judge)
│       └── white_agent.py     # White agent (participant)
├── src/
│   ├── agentbeats/            # AgentBeats framework
│   └── green_agent/           # Shared browser automation code
│       └── task_execution/
│           ├── browser_agent.py    # Playwright automation (529 lines)
│           └── utils/
│               ├── browser_helper.py
│               └── html_cleaner.py
├── data/
│   └── tasks.json             # Task definitions
├── .output/                   # Evaluation results (gitignored)
├── .logs/                     # Log files (gitignored)
├── .env                       # API keys (gitignored)
└── .env.example               # Environment template
```

## Development

### Adding New Tasks

Edit `data/tasks.json`:

```json
{
  "task_id": "unique_id",
  "website": "https://example.com",
  "task_description": "Complete this task...",
  "level": "easy"
}
```

Update `scenario.toml`:

```toml
[config]
task_id = "unique_id"
```

### Modifying Agent Behavior

- **Green agent logic**: Edit `scenarios/web_browser/browser_judge.py`
- **White agent prompts**: Edit `scenarios/web_browser/white_agent.py`
- **Browser automation**: Modify `src/green_agent/task_execution/browser_agent.py`

## Next Steps

See `wabe_implementation_todo.md` for planned improvements and cleanup tasks.

## License

[Add license information]

## Contributing

[Add contribution guidelines]

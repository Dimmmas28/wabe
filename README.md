# WABE - Web Agent Browser Evaluation

A browser automation benchmark using the AgentBeats framework. WABE evaluates AI agents on their ability to navigate websites and complete realistic web tasks using the A2A (Agent-to-Agent) protocol.

## Quick Start

> **Docker Users**: See [Docker Usage](#docker-usage) section for containerized setup.

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

## Docker Usage

### Prerequisites

- Docker installed ([Get Docker](https://docs.docker.com/get-docker/))
- Google API key ([Get API key](https://aistudio.google.com/app/apikey))

### Quick Start (Recommended)

**Using the Python script (easiest):**

```bash
# 1. Create .env file with your API key
echo "GOOGLE_API_KEY=your_api_key_here" > .env

# 2. Run everything with one command
python run-docker.py
```

The script will automatically:
- Build the Docker image (if needed)
- Validate your API key
- Run the evaluation with proper volume mounts
- Show results location

**Options:**
```bash
python run-docker.py --build         # Force rebuild image
python run-docker.py --show-logs     # Show live logs
python run-docker.py --build-only    # Just build, don't run
python run-docker.py --help          # See all options
```

**Using Makefile (alternative):**

```bash
make docker-build    # Build the image
make docker-run      # Run evaluation
make docker-logs     # Run with live logs
make help           # Show all commands
```

### Manual Docker Commands

If you prefer to use Docker directly:

**Build the image:**
```bash
docker build -t wabe:latest .
```

**Run evaluation:**
```bash
# Create .env file first
echo "GOOGLE_API_KEY=your_api_key_here" > .env

# Run with env file
docker run --rm \
  --env-file .env \
  -v $(pwd)/.output:/app/.output \
  -v $(pwd)/.logs:/app/.logs \
  wabe:latest
```

**Run with live logs:**
```bash
docker run --rm \
  --env-file .env \
  -v $(pwd)/.output:/app/.output \
  -v $(pwd)/.logs:/app/.logs \
  wabe:latest \
  uv run agentbeats-run scenarios/web_browser/scenario.toml --show-logs
```

### Output Files

After running, results are available in:
- `.output/results/` - Evaluation results and screenshots
- `.logs/` - Agent logs with timestamps

### Docker Command Reference

| Method | Command | Description |
|--------|---------|-------------|
| **Python Script** | `python run-docker.py` | Build and run (recommended) |
| | `python run-docker.py --show-logs` | Run with live logs |
| | `python run-docker.py --build` | Force rebuild |
| **Makefile** | `make docker-run` | Run evaluation |
| | `make docker-logs` | Run with live logs |
| | `make docker-build` | Build image only |
| **Docker CLI** | `docker build -t wabe .` | Build manually |
| | `docker run --rm --env-file .env wabe` | Run manually |

### Troubleshooting Docker

**API key not working:**
Ensure your `.env` file or `-e` flag has the correct format:
```bash
GOOGLE_API_KEY=AIza...your_key_here
```

**Port already in use:**
```bash
# Check if ports 9009 or 9019 are in use
docker ps
# Stop conflicting containers
docker stop <container_id>
```

**Out of disk space:**
```bash
# Clean up unused Docker resources
docker system prune -a
```

## Architecture

WABE follows the [AgentBeats](https://github.com/google/agentbeats) evaluation framework pattern:

### Components

**Green Agent (Judge)** - `scenarios/web_browser/browser_judge.py`
- Orchestrates browser automation evaluation
- Manages Playwright browser instance
- Sends HTML + task description to white agent via A2A protocol
- Executes actions received from white agent
- Evaluates task completion

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
.output/results/
└── {task_id}/
    ├── result.json      # Evaluation results and metadata
    └── trajectory    
    └── └── step_000.png         # Screenshot(s) of browser state
```

### Example Output JSON

```json
{
  "task_id": "20a460a8fe1971b84411c5b1e6ac4186",
  "task": "Show theatre events for Las Vegas and select one.",
  "final_result_response": "Task failed after 1 steps",
  "action_history": [],
  "thoughts": [],
  "screenshots": [".output/results/20a460a8fe1971b84411c5b1e6ac4186/trajectory/step_000.png"],
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

### Development Scripts

The `scripts/` directory contains shell scripts for code quality and testing:

#### Formatting Code

**Format code automatically:**
```bash
./scripts/format.sh
```
Runs `black` and `isort` to automatically format all Python code.

**Check formatting:**
```bash
./scripts/check-format.sh
```
Verifies code formatting without making changes. (Useful for CI/CD or pre-commit hooks).

#### Running Tests

**Run all tests:**
```bash
./scripts/test.sh
```

**Run specific tests:**
```bash
./scripts/test.sh -v -k test_browser
./scripts/test.sh tests/specific_test.py
```

#### Quality Checks

**Run all quality checks:**
```bash
./scripts/quality-check.sh
```
Runs tests, code formatting checks, and import sorting checks in sequence. Exits on first failure.

#### Before Committing

Run quality checks to ensure code meets project standards:
```bash
./scripts/quality-check.sh
```

Or format code first, then run checks:
```bash
./scripts/format.sh && ./scripts/quality-check.sh
```

## License

[Add license information]

## Contributing

[Add contribution guidelines]

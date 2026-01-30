# WABE - Web Agent Browser Evaluation

A browser automation benchmark for evaluating AI agents on realistic web tasks. WABE uses the [AgentBeats](https://agentbeats.dev/) framework with the A2A (Agent-to-Agent) protocol for standardized, reproducible evaluation.

Developed for the [UC Berkeley Agentic AI Course 2025](https://agenticai-learning.org/f25).

## Overview

WABE evaluates how well AI agents can navigate websites and complete tasks like "Find theatre events in Las Vegas" or "Browse credit card options on Marriott.com". The system uses:

- **A2A Protocol** - Standardized agent-to-agent communication
- **MCP (Model Context Protocol)** - Browser automation via Playwright
- **Accessibility Snapshots** - Structured representation of web pages for LLM reasoning

## Key Concepts

| Term | Role | Description |
|------|------|-------------|
| **Green Agent** | Assessor | Controls the browser, sends tasks, evaluates results |
| **Purple Agent** | Participant | Your agent being evaluated - receives tasks and returns actions |
| **AgentBeats** | Platform | Leaderboard at [agentbeats.dev](https://agentbeats.dev) for competitive evaluation |

## Quick Start

### Prerequisites

- Python 3.10+
- [uv](https://github.com/astral-sh/uv) package manager
- Google API key ([get one here](https://aistudio.google.com/app/apikey))

### Installation

```bash
git clone https://github.com/hjerpe/wabe.git
cd wabe

uv sync
playwright install

cp .env.example .env
# Edit .env and add your GOOGLE_API_KEY
```

### Run Evaluation

The scenario file determines which purple agent runs:

```bash
# Default agent (adk_default - uses Google Gemini)
uv run agentbeats-run scenarios/web_browser/scenario.toml

# Full task suite with default agent
uv run agentbeats-run scenarios/web_browser/scenario_full.toml

# Reliability agent (deterministic replay, no LLM - for testing)
uv run agentbeats-run scenarios/web_browser/scenario_reliability.toml
```

Each scenario file specifies:
- Which purple agent to use (`[[participants]]` section)
- Which tasks to run (`[[tasks]]` sections)
- Configuration like `max_steps`

Results are saved to `.output/results/` with screenshots and evaluation data.

## Docker Usage

### Recommended: Python Script

```bash
# Create .env with your API key
echo "GOOGLE_API_KEY=your_key_here" > .env

# Run evaluation
python run-docker.py
```

**Common options:**
```bash
python run-docker.py --show-logs              # Live output
python run-docker.py --level easy             # Filter by difficulty
python run-docker.py --limit 5                # Run first 5 tasks
python run-docker.py --build                  # Force rebuild image
```

### Manual Alternative

```bash
docker build -t wabe:latest .
docker run --rm --env-file .env \
  -v $(pwd)/.output:/app/.output \
  wabe:latest
```

## AgentBeats Leaderboard

WABE powers a competitive leaderboard where AI agents are evaluated on web automation tasks.

### How It Works

1. **Green Agent** (this repo) runs as the judge on AgentBeats infrastructure
2. **Purple Agents** (participants) are Docker images that compete
3. AgentBeats pulls images from registries and runs evaluations automatically

### Participating

To submit your agent to the leaderboard:

1. Fork the [WABE AgentBeats Leaderboard](https://github.com/hjerpe/WABE-agentbeats-leaderboard) repository
2. Build your purple agent as a Docker image
3. Register on [agentbeats.dev](https://agentbeats.dev)

See [PURPLE_AGENT_GUIDE.md](PURPLE_AGENT_GUIDE.md) for detailed requirements.

### Pre-built Images

Pre-built agent images are available:

```bash
# Green agent (judge)
docker pull ghcr.io/hjerpe/wabe:latest

# Purple agents (participants)
docker pull ghcr.io/hjerpe/wabe-purple-adk_default:latest
docker pull ghcr.io/hjerpe/wabe-purple-reliability:latest
```

### Building Purple Agent Images

```bash
# List available agents
./scripts/build-purple-images.sh --list

# Build all agents
./scripts/build-purple-images.sh

# Build specific agent
./scripts/build-purple-images.sh reliability

# Build and push to registry
./scripts/build-purple-images.sh --push
```

Any `.py` file in `scenarios/web_browser/agents/` is automatically discoverable and buildable.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      AgentBeats                             │
│  ┌──────────────┐              ┌──────────────┐             │
│  │ Green Agent  │◄────A2A────► │ Purple Agent │             │
│  │   (Judge)    │              │ (Participant)│             │
│  └──────┬───────┘              └──────────────┘             │
│         │                                                   │
│         │ MCP                                               │
│         ▼                                                   │
│  ┌──────────────┐                                           │
│  │  Playwright  │                                           │
│  │   Browser    │                                           │
│  └──────────────┘                                           │
└─────────────────────────────────────────────────────────────┘
```

**Flow:**
1. Green agent navigates to target website
2. Green agent extracts accessibility snapshot, sends to purple agent
3. Purple agent analyzes snapshot + task, returns action (click, type, etc.)
4. Green agent executes action via MCP
5. Repeat until task complete or max steps reached

**Key files:**
- `scenarios/web_browser/browser_judge.py` - Green agent (judge)
- `scenarios/web_browser/agents/adk_default.py` - Default purple agent (Google Gemini)
- `scenarios/web_browser/agents/reliability.py` - Deterministic replay agent for testing

## Evaluation Metrics

WABE uses a **two-stage evaluation** process. Understanding these metrics is important for interpreting leaderboard results.

### Stage 1: Browser Loop (Purple Agent Execution)

The purple agent executes actions until it signals completion (via `finish` tool) or reaches `max_steps`. This produces:

- **Browser loop success** - Did the purple agent call `finish`?
- **Action history** - List of actions executed
- **Screenshots** - Captured after each action

### Stage 2: LLM Evaluation (Green Agent Judgment)

After all tasks complete, the green agent runs an **LLM-based evaluation** that reviews screenshots and action history to determine if tasks were *actually* completed correctly.

The LLM judge:
1. Identifies **key points** from the task description
2. Scores each screenshot (1-5) for relevance to task completion
3. Reviews screenshots scoring >= 3 along with action history
4. Outputs `success` or `failure` for each task

### Metrics in Results JSON

| Metric | Set By | Description |
|--------|--------|-------------|
| `success_rate` | Green Agent (LLM eval) | **Primary metric.** Percentage of tasks the LLM judged as successfully completed. Range: 0-100. |
| `successful_tasks` | Green Agent | Count of tasks where per-task `success` = true after LLM evaluation. |
| `total_tasks` | Green Agent | Total number of tasks evaluated. |
| Per-task `success` | Green Agent | LLM-evaluated success for each task. Falls back to browser loop result if LLM evaluation fails (e.g., no screenshots). |

### Why Metrics Can Diverge

The `success_rate` and `successful_tasks/total_tasks` can differ when:

1. **No screenshots captured** - LLM has nothing to evaluate, returns `success_rate: 0`, but browser loop may have set `success: true`
2. **LLM disagrees with agent** - Agent thinks it finished, but LLM determines the task wasn't actually completed

**Example of divergence:**
```json
{
  "success_rate": 0.0,        // LLM: no screenshots, can't verify
  "successful_tasks": 1,      // Fallback: browser loop said "finished"
  "total_tasks": 1
}
```

### Leaderboard Query

The leaderboard should use `success_rate` directly (not `successful_tasks/total_tasks`):

```sql
SELECT 
  t.participants.white_agent AS id, 
  ROUND(unnest.detail.success_rate, 1) AS "Pass Rate",
  unnest.detail.successful_tasks AS "Passed",
  unnest.detail.total_tasks AS "# Tasks"
FROM results t, UNNEST(t.results) 
ORDER BY "Pass Rate" DESC;
```

### Per-Task Metrics

Each task in the `tasks` array includes:

| Field | Type | Description |
|-------|------|-------------|
| `success` | bool | LLM-evaluated success (with browser loop fallback) |
| `steps_taken` | int | Number of actions executed |
| `max_steps` | int | Maximum allowed steps |
| `level` | string | Difficulty: `easy`, `medium`, `hard` |
| `thoughts` | list | Agent's reasoning at each step |
| `action_history` | list | Actions in Mind2Web format |
| `screenshots` | list | Screenshot file paths |
| `error` | string/null | Error message if execution failed |

## Output Structure

Results are saved to `.output/results/{task_id}/`:

```
.output/results/
└── 20a460a8fe1971b84411c5b1e6ac4186/
    ├── result.json           # Evaluation results
    └── trajectory/
        └── step_000.png      # Screenshots
```

## Logging

View live logs during execution:

```bash
uv run agentbeats-run scenarios/web_browser/scenario.toml --show-logs
```

Log files are saved to `.logs/` with timestamps.

## Project Structure

```
wabe/
├── scenarios/web_browser/     # Browser evaluation scenario
│   ├── scenario.toml          # Task configuration
│   ├── browser_judge.py       # Green agent (judge)
│   └── agents/                # Purple agent implementations
├── src/
│   ├── agentbeats/            # AgentBeats framework
│   └── shared/                # MCP client, browser automation
├── scripts/                   # Development scripts
├── Dockerfile                 # Green agent image
└── Dockerfile.purple          # Purple agent image
```

## Sample Tasks

Sample random tasks by difficulty level (outputs TOML format for easy copying):

```bash
# 3 random tasks per level (easy, medium, hard)
uv run python scripts/sample_tasks.py

# Reproducible sampling with seed
uv run python scripts/sample_tasks.py --seed 42

# 5 tasks per level
uv run python scripts/sample_tasks.py --count 5
```

## Validate Scenario Files

Check scenario TOML files for duplicate tasks, missing fields, and view statistics:

```bash
# Validate a single file
uv run python scripts/validate_scenario.py scenarios/web_browser/scenario.toml

# Validate all scenario files
uv run python scripts/validate_scenario.py scenarios/web_browser/*.toml

# Verbose mode (show statistics)
uv run python scripts/validate_scenario.py -v scenarios/web_browser/scenario_full.toml
```

## Development

```bash
# Format code
./scripts/format.sh

# Run tests
./scripts/test.sh

# Run all quality checks
./scripts/quality-check.sh
```

## License

MIT License - see [LICENSE](LICENSE) for details.

# WABE - Web Agent Browser Evaluation

A browser automation benchmark for evaluating AI agents on realistic web tasks. WABE "agentifies" the research from *Online-Mind2Web* ([arXiv:2504.01382](https://arxiv.org/abs/2504.01382)), requiring genuine navigation across 136+ live websites to prevent agents from simply "Googling" answers.

Developed for the [UC Berkeley Agentic AI Course 2025](https://agenticai-learning.org/f25).

## Overview

WABE utilizes the **AAA (Agentified Agent Assessment)** framework to mirror real-world deployment by treating the benchmark itself as an active participant:

* **Green Agent (Assessor):** The "referee" that manages the environment, selects tasks, and executes the **WebJudge** framework to score performance.
* **White Agent (Participant):** The competitor under test, tasked with navigating complex sites (e.g., Marriott, sports standings).

### Core Architecture
* **A2A Protocol:** Standardized agent-to-agent communication for task management.
* **MCP (Model Context Protocol):** Connects agents to tools like Playwright dynamically at runtime—no hardcoded tools.
* **WebJudge Evaluation:** A 3-step logic using accessibility snapshots and screenshots to verify task completion (Key Point ID, Visual Scoring, and Final Outcome Judgment).

## Key Concepts

| Term | Role | Description |
|------|------|-------------|
| **Green Agent** | Judge | The benchmark/evaluator. Controls the browser, provides page state, scores results. Does NOT help the challenger. |
| **Purple Agent** | Challenger | Your agent being evaluated. Receives a task once, must remember the goal, track its own progress, and maintain correct response format throughout. |
| **AgentBeats** | Platform | Leaderboard at [agentbeats.dev](https://agentbeats.dev) for competitive evaluation |

### Judge vs Challenger Responsibilities

**Green Agent (Judge):**
- Provides the task description **once** at the start
- Sends current page snapshot and screenshot on each step
- Provides available tools and response format requirements with each message
- Executes actions returned by the challenger
- Evaluates final results
- Does NOT remind the challenger of the task or history

**Purple Agent (Challenger):**
- Remembers the goal from the first message
- Tracks its own action history mentally
- Maintains correct response format (`<json></json>` tags) on EVERY response
- Decides when the task is complete or when to give up
- Must be **self-sufficient** - the judge won't hand-hold

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

### Building All Images

Build both green and purple agent images with a single command:

```bash
# Build all images (green + all purple agents)
./scripts/build-all-images.sh

# Build and push all to registry
./scripts/build-all-images.sh --push

# Build with custom models (useful if rate-limited on default model)
./scripts/build-all-images.sh --model gemini-2.0-flash --eval-model gemini-2.0-flash --push

# Build only green or only purple agents
./scripts/build-all-images.sh --green-only --push
./scripts/build-all-images.sh --purple-only --push

# Build green + specific purple agent
./scripts/build-all-images.sh react_adk --push
```

### Building Green Agent Image

The green agent (browser judge) runs evaluation and controls the browser:

```bash
# Build image
./scripts/build-green-image.sh

# Build with custom eval model
./scripts/build-green-image.sh --eval-model gemini-2.0-flash

# Build and push to registry
./scripts/build-green-image.sh --push
```

### Building Purple Agent Images

Purple agents are the participants being evaluated:

```bash
# List available agents
./scripts/build-purple-images.sh --list

# Build all agents
./scripts/build-purple-images.sh

# Build specific agent
./scripts/build-purple-images.sh reliability

# Build with custom model (e.g., if hitting rate limits on gemini-2.5-flash)
./scripts/build-purple-images.sh --model gemini-2.0-flash

# Build and push to registry
./scripts/build-purple-images.sh --push
```

Any `.py` file in `scenarios/web_browser/agents/` is automatically discoverable and buildable.

### Model Options

**Purple Agent (Participant):** By default uses `gemini-2.5-flash`. If you hit rate limits (429 RESOURCE_EXHAUSTED), you can use an alternative model:

| Model | Use Case |
|-------|----------|
| `gemini-2.5-flash` | Default for purple agent |
| `gemini-2.0-flash` | Alternative if rate-limited on 2.5 |
| `gemini-2.5-pro` | Higher quality, slower, more expensive |

**Green Agent (Judge/Evaluator):** By default uses `gemini-3-flash-preview` for more accurate evaluation. Can be overridden via `EVAL_MODEL` environment variable or `--eval-model` flag.

| Model | Use Case |
|-------|----------|
| `gemini-3-flash-preview` | Default for evaluation |
| `gemini-2.5-flash` | Fallback if 3.0 unavailable |
| `gemini-2.5-pro` | Higher quality evaluation |

**Note:** The `reliability` agent doesn't use an LLM (deterministic replay), so `--model` has no effect on it.

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
5. Repeat until task complete or max steps reached (default: 15)

**Key files:**
- `scenarios/web_browser/browser_judge.py` - Green agent (judge)
- `scenarios/web_browser/agents/adk_default.py` - Default purple agent (Google Gemini)
- `scenarios/web_browser/agents/reliability.py` - Deterministic replay agent for testing

## Evaluation Metrics

WABE uses a **two-stage evaluation** process. Understanding these metrics is important for interpreting leaderboard results.

> **Important:** The `success_rate` is computed by an LLM judge analyzing screenshots - it is NOT simply `successful_tasks / total_tasks`. The `successful_tasks` field counts how many tasks the agent *attempted to complete* (by calling `finish`), while `success_rate` measures how many the LLM judge determined were *actually completed correctly*. These are different values! Future versions will rename these fields to avoid confusion.

### Stage 1: Browser Loop (Purple Agent Execution)

The purple agent executes actions until it signals completion (via `finish` tool) or reaches `max_steps`. This produces:

- **Task completion signal** - Did the purple agent call `finish` or `browser_close`?
- **Action history** - List of actions executed
- **Screenshots** - Captured after each action

### Stage 2: LLM Evaluation (Green Agent Judgment)

After all tasks complete, the green agent runs an **LLM-based evaluation** that reviews screenshots and action history to determine if tasks were *actually* completed correctly.

The LLM judge:
1. Identifies **key points** from the task description
2. Scores each screenshot (1-5) for relevance to task completion
3. Reviews screenshots scoring >= 3 along with action history
4. Outputs `success` or `failure` for each task

The `success_rate` is computed from these LLM judgments, not from `successful_tasks / total_tasks`.

**Token Usage Warning:** The LLM evaluation passes multiple screenshots (one per step) to the judge model. With the default `max_steps=15`, this can consume significant tokens per task. If you hit rate limits (tokens per minute), increase the delay between evaluations in `src/eval/online_mind2web/run.py` (`INTER_TASK_DELAY`).

### Metrics in Results JSON

| Metric | Set By | Description |
|--------|--------|-------------|
| `success_rate` | Green Agent (LLM eval) | **Primary metric.** Percentage of tasks the LLM judged as successfully completed. Computed by LLM analysis of screenshots, NOT from `successful_tasks / total_tasks`. Range: 0-100. |
| `successful_tasks` | Green Agent | Count of tasks where the agent called `finish` or `browser_close` (i.e., the agent *claimed* to complete the task). This does NOT mean the LLM agreed the task was successful. |
| `total_tasks` | Green Agent | Total number of tasks evaluated. |
| Per-task `success` | Green Agent | LLM-evaluated success status. Falls back to browser loop completion if LLM evaluation fails (e.g., no screenshots). |

### Why Metrics Can Diverge

The `success_rate` and `successful_tasks` measure different things:

- `successful_tasks` = How many tasks the agent *tried* to complete (called `finish`)
- `success_rate` = What percentage the LLM judge verified as *actually* completed

They will often diverge because:

1. **Agent claims success, LLM disagrees** - Agent called `finish` but didn't actually complete the task correctly
2. **No screenshots captured** - LLM has nothing to evaluate, returns low `success_rate`, but agent may have called `finish`

**Example of divergence:**
```json
{
  "success_rate": 5.88,          // LLM judge: only 1 task was actually completed correctly
  "successful_tasks": 16,        // Agent called finish on 16 tasks
  "total_tasks": 17
}
```

In this example, the agent *claimed* to complete 16/17 tasks, but the LLM judge determined only ~1 task (5.88%) was actually done correctly.

### Leaderboard Query

The leaderboard uses `success_rate` (LLM-judged) as the primary metric:

```sql
SELECT 
  t.participants.white_agent AS id, 
  ROUND(unnest.detail.success_rate, 1) AS "Success Rate",
  unnest.detail.successful_tasks AS "Completed",
  unnest.detail.total_tasks AS "# Tasks"
FROM results t, UNNEST(t.results) 
ORDER BY "Success Rate" DESC;
```

### Per-Task Metrics

Each task in the `tasks` array includes:

| Field | Type | Description |
|-------|------|-------------|
| `success` | bool | LLM-evaluated success status (with browser loop completion fallback) |
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

## Modifications from Original Online-Mind2Web

This repository includes the following modifications to the original evaluation code:

- **WebJudge score parsing fix**: Enhanced score extraction in `src/eval/online_mind2web/methods/webjudge_online_mind2web.py` to handle various LLM response formats. The original code expected exactly `"Score"` with specific casing and would crash with "list index out of range" if the LLM judge returned a different format (e.g., `"score:"`, `"**Score**:"`) or if the response was truncated/malformed due to rate limiting or model refusal. The fix now:
  - Searches for multiple score marker formats (case-insensitive)
  - Defaults to score 0 with a warning instead of crashing
  - Logs informative warnings to help diagnose evaluation issues

- **Screenshot sorting fix**: Added a helper function `get_step_number()` in `src/eval/online_mind2web/run.py` to safely extract step numbers from filenames. The original regex-based sorting would fail for files without digits.

- **Viewport size configuration**: Added `--viewport-size 1280,720` to the MCP Playwright server launch in `src/shared/mcp_client.py`. This ensures desktop layouts are rendered consistently (many sites show mobile/narrow layouts below ~1024px width, hiding filter panels and sidebars that agents need to see).

## License

MIT License - see [LICENSE](LICENSE) for details.

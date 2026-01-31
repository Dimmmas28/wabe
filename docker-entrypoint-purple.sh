#!/bin/bash
set -e

# Validate required environment variables
if [ -z "$GOOGLE_API_KEY" ]; then
    echo "ERROR: GOOGLE_API_KEY environment variable is required"
    echo "Run with: docker run -e GOOGLE_API_KEY=your_key ..."
    exit 1
fi

# Parse AgentBeats arguments (--host, --port, --card-url)
HOST="0.0.0.0"
PORT="9019"
CARD_URL=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --host)
            HOST="$2"
            shift 2
            ;;
        --port)
            PORT="$2"
            shift 2
            ;;
        --card-url)
            CARD_URL="$2"
            shift 2
            ;;
        *)
            # Pass remaining args to the command
            break
            ;;
    esac
done

# Export for use by agents
export AGENT_HOST="$HOST"
export AGENT_PORT="$PORT"
export AGENT_CARD_URL="$CARD_URL"

# Resolve agent type (default: adk_default)
AGENT_TYPE="${AGENT_TYPE:-adk_default}"

# Strip .py suffix if user included it
AGENT_TYPE="${AGENT_TYPE%.py}"

# Resolve agent file path
AGENT_FILE="scenarios/web_browser/agents/${AGENT_TYPE}.py"

# Validate agent file exists
if [ ! -f "$AGENT_FILE" ]; then
    echo "ERROR: Unknown agent type '${AGENT_TYPE}'"
    echo "Available agents:"
    for f in scenarios/web_browser/agents/*.py; do
        basename="${f##*/}"
        if [ "$basename" != "__init__.py" ] && [ "$basename" != "__pycache__" ]; then
            echo "  - ${basename%.py}"
        fi
    done
    exit 1
fi

echo "Starting purple agent (${AGENT_TYPE}) on $HOST:$PORT"
if [ -n "$CARD_URL" ]; then
    echo "Agent card URL: $CARD_URL"
fi

# Run the agent
if [ -n "$CARD_URL" ]; then
    exec uv run python "$AGENT_FILE" --host "$HOST" --port "$PORT" --card-url "$CARD_URL"
else
    exec uv run python "$AGENT_FILE" --host "$HOST" --port "$PORT"
fi

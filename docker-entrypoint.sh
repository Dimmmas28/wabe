#!/bin/bash
set -e

# Validate required environment variables
if [ -z "$GOOGLE_API_KEY" ]; then
    echo "ERROR: GOOGLE_API_KEY environment variable is required"
    echo "Run with: docker run -e GOOGLE_API_KEY=your_key ..."
    exit 1
fi

# Create output directories if they don't exist
mkdir -p .output .logs

# Parse AgentBeats arguments (--host, --port, --card-url)
HOST="127.0.0.1"
PORT="9009"
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

echo "Starting agent on $HOST:$PORT"
if [ -n "$CARD_URL" ]; then
    echo "Agent card URL: $CARD_URL"
fi

# If no command provided, run the default scenario with parsed host/port
if [ $# -eq 0 ]; then
    if [ -n "$CARD_URL" ]; then
        exec uv run python scenarios/web_browser/browser_judge.py --host "$HOST" --port "$PORT" --card-url "$CARD_URL"
    else
        exec uv run python scenarios/web_browser/browser_judge.py --host "$HOST" --port "$PORT"
    fi
else
    exec "$@"
fi

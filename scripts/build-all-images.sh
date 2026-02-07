#!/bin/bash
set -e

# Configuration
DEFAULT_REGISTRY="ghcr.io/hjerpe"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Function to show usage
show_usage() {
    cat << 'EOF'
Usage: build-all-images.sh [OPTIONS] [PURPLE_AGENT]

Build both green and purple Docker images for WABE.

Arguments:
  PURPLE_AGENT   Build only this purple agent (e.g., react_adk, adk_default)
                 If omitted, builds all purple agents

Options:
  --push         Push images to registry after building
  --green-only   Build only the green agent
  --purple-only  Build only purple agent(s)
  --registry     Registry prefix (default: ghcr.io/hjerpe)
  --model        Model for purple agent (default: gemini-2.5-flash)
  --eval-model   Eval model for green agent (default: gemini-3-flash-preview)
  -l, --list     List available purple agents
  -h, --help     Show this help message

Examples:
  ./scripts/build-all-images.sh                    # Build all images
  ./scripts/build-all-images.sh --push             # Build and push all
  ./scripts/build-all-images.sh react_adk --push   # Build green + react_adk, push
  ./scripts/build-all-images.sh --green-only       # Build only green agent
  ./scripts/build-all-images.sh --purple-only      # Build all purple agents
  ./scripts/build-all-images.sh --model gemini-2.5-flash --eval-model gemini-2.5-flash

Images produced:
  Green:  wabe:latest
  Purple: wabe-purple-react_adk:latest, wabe-purple-adk_default:latest, etc.

Note: You must be logged into Docker registry before using --push:
  docker login ghcr.io
EOF
}

# Parse arguments
PUSH=""
REGISTRY="$DEFAULT_REGISTRY"
GREEN_ONLY=false
PURPLE_ONLY=false
AGENT=""
PURPLE_MODEL=""
EVAL_MODEL=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --push)
            PUSH="--push"
            shift
            ;;
        --registry)
            REGISTRY="$2"
            shift 2
            ;;
        --green-only)
            GREEN_ONLY=true
            shift
            ;;
        --purple-only)
            PURPLE_ONLY=true
            shift
            ;;
        --model)
            PURPLE_MODEL="$2"
            shift 2
            ;;
        --eval-model)
            EVAL_MODEL="$2"
            shift 2
            ;;
        -l|--list)
            "$SCRIPT_DIR/build-purple-images.sh" --list
            exit 0
            ;;
        -h|--help)
            show_usage
            exit 0
            ;;
        *)
            if [ -z "$AGENT" ]; then
                AGENT="$1"
            fi
            shift
            ;;
    esac
done

# Build model args for sub-scripts
GREEN_MODEL_ARG=""
if [ -n "$EVAL_MODEL" ]; then
    GREEN_MODEL_ARG="--eval-model $EVAL_MODEL"
fi

PURPLE_MODEL_ARG=""
if [ -n "$PURPLE_MODEL" ]; then
    PURPLE_MODEL_ARG="--model $PURPLE_MODEL"
fi

# Build green agent (unless purple-only)
if [ "$PURPLE_ONLY" = false ]; then
    echo "========================================"
    echo "Building GREEN agent (judge)"
    echo "========================================"
    "$SCRIPT_DIR/build-green-image.sh" --registry "$REGISTRY" $GREEN_MODEL_ARG $PUSH
    echo ""
fi

# Build purple agent(s) (unless green-only)
if [ "$GREEN_ONLY" = false ]; then
    echo "========================================"
    echo "Building PURPLE agent(s) (challenger)"
    echo "========================================"
    if [ -n "$AGENT" ]; then
        "$SCRIPT_DIR/build-purple-images.sh" --registry "$REGISTRY" $PURPLE_MODEL_ARG $PUSH "$AGENT"
    else
        "$SCRIPT_DIR/build-purple-images.sh" --registry "$REGISTRY" $PURPLE_MODEL_ARG $PUSH
    fi
    echo ""
fi

echo "========================================"
echo "All builds complete!"
echo "========================================"

if [ -n "$PUSH" ]; then
    echo ""
    echo "Images pushed to registry: $REGISTRY"
    echo ""
    echo "REMINDER: New packages default to PRIVATE on ghcr.io"
    echo "To make public: https://github.com/users/hjerpe/packages"
fi

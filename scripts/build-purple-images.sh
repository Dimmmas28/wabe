#!/bin/bash
set -e

# Configuration
DEFAULT_REGISTRY="ghcr.io/hjerpe"
IMAGE_BASE="wabe-purple"
AGENTS_DIR="scenarios/web_browser/agents"

# Function to show usage
show_usage() {
    cat << 'EOF'
Usage: build-purple-images.sh [OPTIONS] [AGENT_NAME]

Build per-agent Docker images for WABE purple agents.

Arguments:
  AGENT_NAME    Build only this agent (e.g., reliability, adk_default)
                If omitted, builds all agents in scenarios/web_browser/agents/

Options:
  --push        Push images to registry after building
  --registry    Registry prefix (default: ghcr.io/hjerpe)
  -h, --help    Show this help message

Examples:
  ./scripts/build-purple-images.sh                    # Build all agents
  ./scripts/build-purple-images.sh reliability        # Build reliability agent
  ./scripts/build-purple-images.sh --push             # Build all and push
  ./scripts/build-purple-images.sh reliability --push # Build and push one

Images produced:
  wabe-purple-adk_default
  wabe-purple-reliability
  (etc. for each agent in agents/ directory)

Note: You must be logged into Docker registry before using --push:
  docker login ghcr.io
EOF
}

# Parse arguments
PUSH=false
REGISTRY="$DEFAULT_REGISTRY"
AGENT=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --push)
            PUSH=true
            shift
            ;;
        --registry)
            REGISTRY="$2"
            shift 2
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

# Function to list available agents
list_agents() {
    for f in ${AGENTS_DIR}/*.py; do
        basename="${f##*/}"
        if [ "$basename" != "__init__.py" ]; then
            echo "${basename%.py}"
        fi
    done
}

# Function to build single agent
build_agent() {
    local agent=$1
    local image_name="${IMAGE_BASE}-${agent}"
    local full_tag="${REGISTRY}/${image_name}:latest"
    
    echo "Building ${image_name}..."
    if ! docker build \
        --build-arg AGENT_TYPE="$agent" \
        -t "$image_name" \
        -t "$full_tag" \
        -f Dockerfile.purple .; then
        echo "ERROR: Docker build failed for ${agent}"
        exit 2
    fi
    
    if [ "$PUSH" = true ]; then
        echo "Pushing ${full_tag}..."
        if ! docker push "$full_tag"; then
            echo "ERROR: Docker push failed for ${full_tag}. Are you logged in?"
            exit 3
        fi
    fi
}

# Validate agent if specified
if [ -n "$AGENT" ]; then
    AGENT_FILE="${AGENTS_DIR}/${AGENT}.py"
    if [ ! -f "$AGENT_FILE" ]; then
        echo "ERROR: Unknown agent '${AGENT}'"
        echo "Available agents:"
        list_agents | sed 's/^/  - /'
        exit 1
    fi
    build_agent "$AGENT"
else
    # Build all agents
    for agent in $(list_agents); do
        build_agent "$agent"
    done
fi

echo "Done!"

# Show visibility reminder if we pushed images
if [ "$PUSH" = true ]; then
    echo ""
    echo "=========================================="
    echo "IMPORTANT: Package visibility on ghcr.io"
    echo "=========================================="
    echo "New packages default to PRIVATE. To make public:"
    echo "1. Go to: https://github.com/users/hjerpe/packages"
    echo "2. Click on the package (e.g., wabe-purple-reliability)"
    echo "3. Package settings → Change visibility → Public"
    echo ""
fi

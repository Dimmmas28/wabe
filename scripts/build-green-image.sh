#!/bin/bash
set -e

# Configuration
DEFAULT_REGISTRY="ghcr.io/hjerpe"
IMAGE_NAME="wabe"

# Function to show usage
show_usage() {
    cat << 'EOF'
Usage: build-green-image.sh [OPTIONS]

Build the Docker image for the WABE green agent (browser judge).

Options:
  --push         Push image to registry after building
  --registry     Registry prefix (default: ghcr.io/hjerpe)
  --eval-model   Eval model for green agent (default: gemini-3-flash-preview)
  -h, --help     Show this help message

Examples:
  ./scripts/build-green-image.sh                           # Build with defaults
  ./scripts/build-green-image.sh --eval-model gemini-2.5-flash  # Custom model
  ./scripts/build-green-image.sh --push                    # Build and push

Image produced:
  wabe:latest (local)
  ghcr.io/hjerpe/wabe:latest (registry)

Note: You must be logged into Docker registry before using --push:
  docker login ghcr.io
EOF
}

# Parse arguments
PUSH=false
REGISTRY="$DEFAULT_REGISTRY"
EVAL_MODEL=""

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
        --eval-model)
            EVAL_MODEL="$2"
            shift 2
            ;;
        -h|--help)
            show_usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

FULL_TAG="${REGISTRY}/${IMAGE_NAME}:latest"

# Build docker build args
BUILD_ARGS=""
if [ -n "$EVAL_MODEL" ]; then
    BUILD_ARGS="--build-arg EVAL_MODEL=$EVAL_MODEL"
    echo "Using eval model: $EVAL_MODEL"
fi

echo "Building ${IMAGE_NAME}..."
if ! docker build \
    $BUILD_ARGS \
    -t "$IMAGE_NAME" \
    -t "$FULL_TAG" \
    -f Dockerfile .; then
    echo "ERROR: Docker build failed"
    exit 2
fi

echo "Build successful: ${IMAGE_NAME}:latest"

if [ "$PUSH" = true ]; then
    echo "Pushing ${FULL_TAG}..."
    if ! docker push "$FULL_TAG"; then
        echo "ERROR: Docker push failed for ${FULL_TAG}. Are you logged in?"
        exit 3
    fi
    echo "Push successful: ${FULL_TAG}"
    
    echo ""
    echo "=========================================="
    echo "IMPORTANT: Package visibility on ghcr.io"
    echo "=========================================="
    echo "New packages default to PRIVATE. To make public:"
    echo "1. Go to: https://github.com/users/hjerpe/packages"
    echo "2. Click on the package (wabe)"
    echo "3. Package settings -> Change visibility -> Public"
    echo ""
fi

echo "Done!"

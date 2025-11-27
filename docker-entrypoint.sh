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

# Execute the command passed to docker run
exec "$@"

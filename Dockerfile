# Use Playwright base image with pre-installed browsers (Ubuntu 24.04 with Python 3.12)
FROM mcr.microsoft.com/playwright/python:v1.55.0-noble

# Set working directory
WORKDIR /app

# Install build dependencies for Python packages with native extensions
RUN apt-get update && \
    apt-get install -y build-essential && \
    rm -rf /var/lib/apt/lists/*

# Install uv package manager
RUN pip install --no-cache-dir uv

# Copy dependency files and README (needed for package build)
COPY pyproject.toml uv.lock README.md ./

# Install Python dependencies using uv with frozen lock file
# Explicitly specify system Python path
RUN uv sync --frozen --python /usr/bin/python3

# Copy project source code
COPY src/ ./src/
COPY scenarios/ ./scenarios/
COPY data/ ./data/
COPY .env.example ./.env.example

# Create output directories
RUN mkdir -p .output .logs

# Set environment variables for non-interactive mode
ENV PYTHONUNBUFFERED=1
ENV GOOGLE_GENAI_USE_VERTEXAI=FALSE
ENV HEADLESS=true

# Expose ports for both agents
EXPOSE 9009 9019

# Copy and set up entrypoint script
COPY docker-entrypoint.sh /app/
RUN chmod +x /app/docker-entrypoint.sh

# Use validation entrypoint
ENTRYPOINT ["/app/docker-entrypoint.sh"]

# Default command runs the evaluation
CMD ["uv", "run", "agentbeats-run", "scenarios/web_browser/scenario.toml"]

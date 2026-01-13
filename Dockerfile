# Use Playwright base image with pre-installed browsers (Ubuntu 24.04 with Python 3.12)
FROM mcr.microsoft.com/playwright/python:v1.55.0-noble

# Set working directory
WORKDIR /app

# Install Node.js 22.x LTS via NodeSource repository
RUN apt-get update && \
    apt-get install -y ca-certificates curl gnupg && \
    mkdir -p /etc/apt/keyrings && \
    curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | \
    gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg && \
    echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_22.x nodistro main" | \
    tee /etc/apt/sources.list.d/nodesource.list && \
    apt-get update && \
    apt-get install -y nodejs && \
    rm -rf /var/lib/apt/lists/*

# Install Chromium browser and system dependencies for Playwright MCP server
# Note: Due to a known issue in @playwright/mcp v0.0.33+ (GitHub Issue #914),
# the browser may not be detected initially. The agent will automatically install
# it at runtime using the MCP server's browser_install tool.
RUN npx -y playwright install chromium --with-deps

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

# Default command runs the evaluation with default scenario
# Override at runtime: docker run ... wabe:latest uv run agentbeats-run <custom-scenario.toml>
CMD ["uv", "run", "agentbeats-run", "scenarios/web_browser/scenario.toml"]

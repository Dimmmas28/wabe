.PHONY: help docker-build docker-run docker-logs docker-shell docker-clean

# Default scenario file
SCENARIO ?= scenarios/web_browser/scenario.toml

# Task filtering variables (optional)
LIMIT ?=
LEVEL ?=

# Default target
help:
	@echo "WABE Docker Commands"
	@echo ""
	@echo "  make docker-build                Build the Docker image"
	@echo "  make docker-run                  Run evaluation in Docker"
	@echo "  make docker-logs                 Run with live logs"
	@echo "  make docker-shell                Open shell in container"
	@echo "  make docker-clean                Remove Docker image"
	@echo ""
	@echo "Use variables to customize execution:"
	@echo "  make docker-run SCENARIO=scenarios/web_browser/scenario_full.toml"
	@echo "  make docker-run LEVEL=easy"
	@echo "  make docker-run LIMIT=5"
	@echo "  make docker-run LEVEL=hard LIMIT=3"
	@echo ""
	@echo "Alternative: Use run-docker.py for more options"
	@echo "  python run-docker.py --help"

# Build Docker image
docker-build:
	docker build -t wabe:latest .

# Run evaluation
docker-run:
	@if [ ! -f .env ] && [ -z "$$GOOGLE_API_KEY" ]; then \
		echo "Error: GOOGLE_API_KEY not found"; \
		echo "Create .env file: echo 'GOOGLE_API_KEY=your_key' > .env"; \
		exit 1; \
	fi
	docker run --rm \
		--env-file .env \
		$(if $(LIMIT),-e TASK_LIMIT=$(LIMIT)) \
		$(if $(LEVEL),-e TASK_LEVEL=$(LEVEL)) \
		-v $$(pwd)/.output:/app/.output \
		-v $$(pwd)/.logs:/app/.logs \
		wabe:latest \
		uv run agentbeats-run $(SCENARIO)

# Run with live logs
docker-logs:
	@if [ ! -f .env ] && [ -z "$$GOOGLE_API_KEY" ]; then \
		echo "Error: GOOGLE_API_KEY not found"; \
		echo "Create .env file: echo 'GOOGLE_API_KEY=your_key' > .env"; \
		exit 1; \
	fi
	docker run --rm \
		--env-file .env \
		$(if $(LIMIT),-e TASK_LIMIT=$(LIMIT)) \
		$(if $(LEVEL),-e TASK_LEVEL=$(LEVEL)) \
		-v $$(pwd)/.output:/app/.output \
		-v $$(pwd)/.logs:/app/.logs \
		wabe:latest \
		uv run agentbeats-run $(SCENARIO) --show-logs

# Open interactive shell in container (for debugging)
docker-shell:
	docker run --rm -it \
		-e GOOGLE_API_KEY=dummy_key_for_shell \
		--entrypoint /bin/bash \
		wabe:latest

# Remove Docker image
docker-clean:
	docker rmi wabe:latest

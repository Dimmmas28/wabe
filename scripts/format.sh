#!/bin/bash
# Format code with black and isort
echo "🎨 Formatting code..."

echo "1/2 Running black..."
uv run black .

echo "2/2 Running isort..."
uv run isort .

echo "✅ Code formatting complete!"

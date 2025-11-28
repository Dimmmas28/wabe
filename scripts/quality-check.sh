#!/bin/bash
# Run all quality checks
echo "🚀 Running quality checks..."

echo "1/3 📋 Running tests..."
uv run pytest
if [ $? -ne 0 ]; then
    echo "❌ Tests failed!"
    exit 1
fi

echo "2/3 🔍 Checking code formatting..."
uv run black --check --diff .
if [ $? -ne 0 ]; then
    echo "❌ Code formatting issues found!"
    exit 1
fi

echo "3/3 📄 Checking import sorting..."
uv run isort --check-only --diff .
if [ $? -ne 0 ]; then
    echo "❌ Import sorting issues found!"
    exit 1
fi

echo "🧹 Code quality checks complete!"
echo "✅ All quality checks passed!"

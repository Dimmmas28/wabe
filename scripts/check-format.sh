#!/bin/bash
# Check code formatting without making changes
echo "🔍 Checking code formatting..."

echo "1/2 Checking black formatting..."
uv run black --check --diff .
BLACK_EXIT=$?

echo "2/2 Checking isort..."
uv run isort --check-only --diff .
ISORT_EXIT=$?

if [ $BLACK_EXIT -eq 0 ] && [ $ISORT_EXIT -eq 0 ]; then
    echo "✅ Code formatting is correct!"
    exit 0
else
    echo "❌ Code formatting issues found. Run scripts/format.sh to fix."
    exit 1
fi

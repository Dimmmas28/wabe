#!/bin/bash
# Run tests with pytest
echo "🧪 Running tests..."

uv run pytest "$@"

if [ $? -eq 0 ]; then
    echo "✅ All tests passed!"
else
    echo "❌ Some tests failed!"
    exit 1
fi

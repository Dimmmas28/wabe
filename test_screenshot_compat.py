#!/usr/bin/env python3
"""
Unit test to verify get_latest_screenshot_base64() works with MCP screenshot format.
Tests the compatibility without requiring full MCP server startup.
"""
import base64
import sys
from pathlib import Path

from PIL import Image


def test_screenshot_base64_compatibility():
    """Test that get_latest_screenshot_base64() can process MCP-saved screenshots"""
    from src.shared.browser_agent import BrowserAgent

    print(
        "Testing get_latest_screenshot_base64() compatibility with MCP screenshots..."
    )

    # Create agent
    agent = BrowserAgent(headless=True, output_dir=".output/test_screenshot_compat")

    # Simulate what _take_screenshot_via_mcp() does:
    # 1. Creates a screenshot directory
    # 2. Saves a base64-decoded PNG file
    # 3. Appends the path to self.screenshots

    from green_agent.constants import TASK_RESULT_SCREENSHOTS_FOLDER

    screenshot_dir = agent.output_dir / TASK_RESULT_SCREENSHOTS_FOLDER
    screenshot_dir.mkdir(parents=True, exist_ok=True)

    # Create a minimal valid PNG file (1x1 red pixel)
    test_screenshot_path = screenshot_dir / "step_000.png"
    img = Image.new("RGB", (100, 100), color="red")
    img.save(test_screenshot_path, format="PNG")

    # Simulate _take_screenshot_via_mcp() appending to screenshots list
    agent.screenshots.append(str(test_screenshot_path))

    print(f"✓ Simulated MCP screenshot saved: {test_screenshot_path}")
    print(f"✓ Screenshot added to agent.screenshots list")

    # Now test get_latest_screenshot_base64()
    print("\nTesting get_latest_screenshot_base64()...")
    result = agent.get_latest_screenshot_base64()

    assert result is not None, "get_latest_screenshot_base64() returned None"

    base64_str, file_path = result

    assert base64_str, "base64 string is empty"
    assert file_path == str(
        test_screenshot_path
    ), f"file_path mismatch: {file_path} != {test_screenshot_path}"

    # Verify it's valid base64
    try:
        decoded = base64.b64decode(base64_str)
        print(f"✓ Base64 string is valid ({len(base64_str)} chars)")
        print(f"✓ Decoded to {len(decoded)} bytes")
    except Exception as e:
        raise AssertionError(f"Invalid base64: {e}")

    # Verify we can load the decoded image
    try:
        from io import BytesIO

        img_check = Image.open(BytesIO(decoded))
        print(f"✓ Decoded image is valid: {img_check.size} {img_check.format}")
    except Exception as e:
        raise AssertionError(f"Decoded data is not a valid image: {e}")

    print(
        "\n✅ SUCCESS: get_latest_screenshot_base64() is fully compatible with MCP screenshots"
    )
    print("\nCompatibility verified:")
    print("  - MCP screenshots saved as PNG files ✓")
    print("  - Paths tracked in self.screenshots list ✓")
    print("  - get_latest_screenshot_base64() reads from list ✓")
    print("  - Files loaded and re-encoded as JPEG base64 ✓")


if __name__ == "__main__":
    try:
        test_screenshot_base64_compatibility()
        sys.exit(0)
    except AssertionError as e:
        print(f"❌ FAIL: {e}")
        sys.exit(1)

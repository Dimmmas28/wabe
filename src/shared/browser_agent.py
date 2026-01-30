import asyncio
import base64
import io
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from PIL import Image

from green_agent.constants import TASK_RESULT_FILE_NAME, TASK_RESULT_SCREENSHOTS_FOLDER
from shared.mcp_client import MCPBrowserClient

logger = logging.getLogger(__name__)


class BrowserAgent:
    """
    Browser agent using MCP (Model Context Protocol) for browser automation
    - Runs browser via MCP server
    - Dynamically discovers available tools
    - Executes actions through MCP client
    - Records action history
    - Takes screenshots
    """

    def __init__(self, output_dir: str = "./output"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True, parents=True)

        # State
        self.action_history: List[str] = []
        self.screenshots: List[str] = []
        self.step_count: int = 0
        self.current_url: str = ""
        self.screenshot_failures: int = 0

        # MCP client for browser automation
        self.mcp_client: Optional[MCPBrowserClient] = None

    async def start(self, url: str):
        """Start browser via MCP and navigate to URL"""
        logger.info("🚀 Starting MCP browser client...")

        # Initialize and start MCP client
        self.mcp_client = MCPBrowserClient()
        await self.mcp_client.start()

        logger.info("Installing browser")
        try:
            await self.mcp_client.call_tool("browser_install")
        except Exception as e:
            logger.info("Failed to install browser")
            logger.error(e)
            raise

        logger.info(f"🌐 Navigating to: {url}")

        try:
            # Navigate using MCP client
            await self.mcp_client.call_tool("browser_navigate", url=url)
            self.current_url = url  # Track current URL
        except Exception as e:
            logger.info("Failed to navigate via MCP")
            logger.error(e)
            raise

        # Take initial screenshot via MCP using helper method with retry
        initial_screenshot = None
        for attempt in range(3):
            try:
                initial_screenshot = await self._take_screenshot_via_mcp("step_000")
                if initial_screenshot:
                    break
                logger.warning(
                    f"Initial screenshot attempt {attempt + 1} returned None, retrying..."
                )
                await asyncio.sleep(1)  # Wait for page to render
            except Exception as e:
                logger.warning(f"Initial screenshot attempt {attempt + 1} failed: {e}")
                if attempt < 2:
                    await asyncio.sleep(1)

        if not initial_screenshot:
            logger.error("Failed to capture initial screenshot after 3 attempts")

        print(f"✓ MCP Browser ready at {url}")

    async def stop(self):
        """Stop MCP browser client and clean up resources"""
        if self.mcp_client:
            await self.mcp_client.stop()
            print("🛑 MCP Browser client stopped")
        else:
            logger.warning("MCP client was not initialized")

    async def execute_action(self, tool_name: str, **params) -> Dict[str, Any]:
        """
        Execute an action via MCP client.

        Args:
            tool_name: Name of MCP tool to execute
            **params: Parameters for the tool

        Returns:
            Dict with success status and result
        """
        if not self.mcp_client:
            return {"success": False, "error": "MCP client not started"}

        result = {"success": False, "tool": tool_name, "params": params}

        # INTERCEPT: Check if this is a snapshot request (read-only, not a user action)
        is_snapshot_action = tool_name.lower() in [
            "browser_snapshot",
            "snapshot",
        ]

        if is_snapshot_action:
            # Don't increment step_count - this is not a user action
            logger.info(f"Snapshot request: {tool_name.upper()} (not counting as step)")

            try:
                mcp_result = await self.mcp_client.call_tool(tool_name, **params)
                result["success"] = True
                result["mcp_response"] = mcp_result

                # Record in action history for debugging
                action_str = self._format_action_for_history(tool_name, params)
                self.action_history.append(action_str)
                logger.info(f"✓ {action_str} (snapshot only)")

            except Exception as e:
                result["error"] = str(e)
                logger.error(f"✗ Snapshot failed: {e}")

            return result

        # Increment step count for actual user actions
        self.step_count += 1
        logger.info(f"Step {self.step_count}: {tool_name.upper()}")

        # INTERCEPT: Check if this is a browser close request
        is_close_action = tool_name.lower() in [
            "browser_close",
            "close",
            "browser_quit",
            "quit",
        ]

        if is_close_action:
            # DO NOT execute close on MCP/Playwright
            # Just record it and signal shutdown
            logger.warning(
                "⚠️ Browser close requested - intercepting (not executing on browser)"
            )

            # Take final screenshot BEFORE close to capture end state for evaluation
            logger.info("Taking final screenshot before close...")
            try:
                await self._take_screenshot_via_mcp(f"step_{self.step_count:03d}_final")
            except Exception as e:
                logger.warning(f"Failed to take final screenshot: {e}")

            result["success"] = True
            result["browser_closed"] = True

            # Record action in history
            action_str = self._format_action_for_history(tool_name, params)
            self.action_history.append(action_str)
            logger.info(f"✓ {action_str}")

            return result

        # Normal execution path for non-close actions
        try:
            # Call MCP tool dynamically - no hardcoded routing
            mcp_result = await self.mcp_client.call_tool(tool_name, **params)
            result["success"] = True
            result["mcp_response"] = mcp_result

            # Track URL changes for navigation actions
            if "navigate" in tool_name.lower() or "goto" in tool_name.lower():
                self.current_url = params.get("url", self.current_url)

            # Record action in Mind2Web format for evaluation
            action_str = self._format_action_for_history(tool_name, params)
            self.action_history.append(action_str)
            logger.info(f"✓ {action_str}")

            # Take screenshot after successful action
            await self._take_screenshot_via_mcp(f"step_{self.step_count:03d}")

        except Exception as e:
            result["error"] = str(e)
            logger.error(f"✗ Failed: {e}")

        return result

    def _format_action_for_history(self, tool_name: str, params: Dict[str, Any]) -> str:
        """
        Format action for history in Mind2Web style.

        CRITICAL: Evaluation scripts parse this exact format.
        Format: <element_description> -> ACTION: value

        Args:
            tool_name: MCP tool name (e.g., "browser_click", "browser_type")
            params: Tool parameters from MCP call

        Returns:
            Formatted action string for action_history
        """
        # Extract element description from params
        # Try common parameter names used by MCP tools
        element = (
            params.get("element")
            or params.get("ref")
            or params.get("selector")
            or params.get("description")
            or "unknown"
        )

        # Normalize tool name to action type
        tool_lower = tool_name.lower()

        # Handle browser close actions
        if "close" in tool_lower or "quit" in tool_lower:
            return "<unknown> -> BROWSER_CLOSE"

        if "click" in tool_lower:
            return f"<{element}> -> CLICK"
        elif "type" in tool_lower or "fill" in tool_lower:
            text = params.get("text", params.get("value", ""))
            return f"<{element}> -> TYPE: {text}"
        elif "select" in tool_lower:
            value = params.get("value", "")
            if not value:
                values = params.get("values", [])
                if isinstance(values, list) and values:
                    value = values[0]
                elif values:
                    value = str(values)
            return f"<{element}> -> SELECT: {value}"
        elif "scroll" in tool_lower:
            direction = params.get("direction", "down")
            return f"<{element}> -> SCROLL: {direction}"
        elif "hover" in tool_lower:
            return f"<{element}> -> HOVER"
        elif "navigate" in tool_lower or "goto" in tool_lower:
            url = params.get("url", "")
            return f"<navigation> -> GOTO: {url}"
        else:
            # Generic format for unknown tools
            return f"<{element}> -> {tool_name.upper()}"

    async def _take_screenshot_via_mcp(self, name: str) -> Optional[str]:
        """
        Take screenshot via MCP and save to filesystem.

        This method captures a screenshot using the MCP client and saves it
        to the correct path format required by evaluation scripts.

        Args:
            name: Screenshot name (e.g., "step_001")

        Returns:
            Path to saved screenshot, or None if failed
        """
        if not self.mcp_client:
            logger.warning("MCP client not initialized")
            return None

        try:
            result = await self.mcp_client.call_tool(
                "browser_take_screenshot", type="png"
            )

            # Extract base64 data from result
            # MCP server returns: {'content': [{'type': 'image', 'data': 'base64...'}]}
            image_data = None
            if isinstance(result, dict):
                # Check for MCP content array format
                if "content" in result and isinstance(result["content"], list):
                    for item in result["content"]:
                        if isinstance(item, dict) and item.get("type") == "image":
                            image_data = item.get("data")
                            break
                # Fallback to simple formats
                if not image_data:
                    image_data = (
                        result.get("data")
                        or result.get("screenshot")
                        or result.get("image")
                    )
            else:
                image_data = str(result)

            if not image_data:
                logger.warning(
                    f"No image data in screenshot response. Response keys: {result.keys() if isinstance(result, dict) else 'N/A'}"
                )
                return None

            # Decode base64 and save to trajectory folder
            screenshot_dir = self.output_dir / TASK_RESULT_SCREENSHOTS_FOLDER
            screenshot_dir.mkdir(parents=True, exist_ok=True)
            screenshot_path = screenshot_dir / f"{name}.png"

            image_bytes = base64.b64decode(image_data)
            with open(screenshot_path, "wb") as f:
                f.write(image_bytes)

            # Track in screenshots list
            path_str = str(screenshot_path)
            self.screenshots.append(path_str)
            logger.info(f"📸 Screenshot saved: {screenshot_path}")

            return path_str

        except Exception as e:
            self.screenshot_failures += 1
            logger.error(f"Failed to take screenshot via MCP: {e}")
            return None

    def get_action_history(self) -> List[str]:
        """Get action history"""
        return self.action_history.copy()

    def get_screenshots(self) -> List[str]:
        """Get list of screenshot paths"""
        return self.screenshots.copy()

    def get_latest_screenshot_base64(
        self, max_width: int = 1280, quality: int = 80
    ) -> tuple[str, str] | None:
        """
        Get the latest screenshot as base64-encoded string.
        Compresses and resizes the image to reduce payload size.

        Args:
            max_width: Maximum width for resizing (default: 1280px)
            quality: JPEG quality 1-100 (default: 80)

        Returns:
            Tuple of (base64_string, file_path) or None if no screenshots exist
        """
        if not self.screenshots:
            return None

        latest_screenshot_path = self.screenshots[-1]

        try:
            # Open and resize image
            img = Image.open(latest_screenshot_path)

            # Resize if width exceeds max_width
            if img.width > max_width:
                ratio = max_width / img.width
                new_height = int(img.height * ratio)
                img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)

            # Convert to RGB if necessary (JPEG doesn't support transparency)
            if img.mode in ("RGBA", "LA", "P"):
                background = Image.new("RGB", img.size, (255, 255, 255))
                if img.mode == "P":
                    img = img.convert("RGBA")
                background.paste(
                    img, mask=img.split()[-1] if img.mode in ("RGBA", "LA") else None
                )
                img = background

            # Save to bytes as JPEG with compression
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=quality, optimize=True)
            image_bytes = buffer.getvalue()

            # Encode to base64
            base64_string = base64.b64encode(image_bytes).decode("utf-8")

            logger.info(
                f"Encoded screenshot {Path(latest_screenshot_path).name}: "
                f"{len(image_bytes)} bytes (JPEG {quality}% quality, {img.width}x{img.height})"
            )

            return base64_string, latest_screenshot_path
        except Exception as e:
            logger.error(f"Failed to encode screenshot {latest_screenshot_path}: {e}")
            return None

    async def get_snapshot(self) -> str:
        """
        Get accessibility snapshot of current page via MCP.

        Returns:
            Accessibility tree text with element refs in format:
            - button "Search" [ref=s12]
            - link "About" [ref=s13]
        """
        if not self.mcp_client:
            logger.error("MCP client not initialized")
            return ""

        try:
            result = await self.mcp_client.call_tool("browser_snapshot")
            # Extract snapshot text from result
            if isinstance(result, dict) and "snapshot" in result:
                return result["snapshot"]
            elif isinstance(result, str):
                return result
            else:
                logger.warning(f"Unexpected snapshot result format: {type(result)}")
                return str(result)
        except Exception as e:
            logger.error(f"Failed to get snapshot via MCP: {e}")
            return ""

    async def get_tools(self) -> List[Dict[str, Any]]:
        """
        Get list of available MCP tools with their schemas.

        Returns:
            List of tool schemas from MCP server, or empty list if not initialized
        """
        if not self.mcp_client:
            logger.warning("MCP client not initialized")
            return []

        try:
            return await self.mcp_client.list_tools()
        except Exception as e:
            logger.error(f"Failed to get tools from MCP: {e}")
            return []

    def save_session(
        self,
        task_id: str,
        task_description: str,
        final_response: str = "",
        thoughts: list[str] = [],
    ):
        """
        Save session data in the format you specified
        """
        # Ensure trajectory directory exists (required by evaluation scripts)
        trajectory_dir = self.output_dir / TASK_RESULT_SCREENSHOTS_FOLDER
        trajectory_dir.mkdir(parents=True, exist_ok=True)

        session_data = {
            "task_id": task_id,
            "task": task_description,
            "final_result_response": final_response
            or f"Completed {len(self.action_history)} actions",
            "action_history": self.action_history,
            "thoughts": thoughts,  # This would come from the agent
            "screenshots": self.screenshots,
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "total_steps": self.step_count,
                "final_url": self.current_url,
                "screenshot_count": len(self.screenshots),
                "screenshot_failures": self.screenshot_failures,
            },
        }

        output_file = self.output_dir / f"{TASK_RESULT_FILE_NAME}.json"
        with open(output_file, "w") as f:
            json.dump(session_data, f, indent=2)

        print(f"\n💾 Session saved to: {output_file}")

        # Log screenshot summary
        if self.screenshot_failures > 0:
            logger.warning(
                f"⚠️ Screenshot summary: {len(self.screenshots)} captured, "
                f"{self.screenshot_failures} failed"
            )
        else:
            logger.info(f"📸 Screenshots captured: {len(self.screenshots)}")

        return session_data

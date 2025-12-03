import asyncio
import base64
import io
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from PIL import Image
from playwright.async_api import Browser, Page, async_playwright

from green_agent.constants import TASK_RESULT_FILE_NAME, TASK_RESULT_SCREENSHOTS_FOLDER
from shared.browser_helper import normal_launch_async, normal_new_context_async
from shared.html_cleaner import HTMLCleaner

logger = logging.getLogger(__name__)


class BrowserAgent:
    """
    Bare minimum browser agent with Playwright
    - Runs browser
    - Defines tools
    - Executes actions
    - Records action history
    - Takes screenshots
    """

    def __init__(self, headless: bool = False, output_dir: str = "./output"):
        self.headless = headless
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True, parents=True)

        # State
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        self.action_history: List[str] = []
        self.screenshots: List[str] = []
        self.step_count: int = 0

        # Tools definition
        self.tools = self._define_tools()

        self.html_cleaner = HTMLCleaner()

    def _define_tools(self) -> List[Dict[str, Any]]:
        """Define available tools/actions"""
        return [
            {
                "name": "click",
                "description": "Click on an element",
                "parameters": {
                    "selector": {
                        "type": "string",
                        "description": "CSS selector or XPath of element to click",
                        "required": True,
                    }
                },
            },
            {
                "name": "type",
                "description": "Type text into an input element",
                "parameters": {
                    "selector": {
                        "type": "string",
                        "description": "CSS selector or XPath of input element",
                        "required": True,
                    },
                    "text": {
                        "type": "string",
                        "description": "Text to type",
                        "required": True,
                    },
                },
            },
            {
                "name": "select",
                "description": "Select an option from dropdown",
                "parameters": {
                    "selector": {
                        "type": "string",
                        "description": "CSS selector or XPath of select element",
                        "required": True,
                    },
                    "value": {
                        "type": "string",
                        "description": "Value to select",
                        "required": True,
                    },
                },
            },
            # {
            #     "name": "get_page_info",
            #     "description": "Get current page URL and title",
            #     "parameters": {},
            # },
        ]

    async def page_on_navigation_handler(self, frame):
        print("page_on_navigation_handler")

    async def page_on_close_handler(self, page: Page):
        logger.info("page_on_close_handler")

    async def page_on_crash_handler(self, page: Page):
        logger.info(f"Page crashed: {page.url}")
        logger.info("Try to reload")
        await page.reload()

    async def page_on_open_handler(self, page: Page):
        page.on("framenavigated", self.page_on_navigation_handler)
        page.on("close", self.page_on_close_handler)
        page.on("crash", self.page_on_crash_handler)

        self.page = page

    async def start(self, url: str):
        """Start browser and navigate to URL"""
        print("🚀 Starting browser...")
        playwright = await async_playwright().start()
        self.browser = await normal_launch_async(
            playwright, headless=self.headless, args=["--start-maximized"]
        )

        context = await normal_new_context_async(self.browser)

        context.on("page", self.page_on_open_handler)

        await context.new_page()

        if not self.page:
            raise ValueError("Page must exist")

        try:
            print(f"🌐 Navigating to: {url}")
            await self.page.goto(url, wait_until="load")  # load or networkidle
        except Exception as e:
            logger.info("Failed to fully load the webpage before timeout")
            logger.error(e)

            return

        # Take initial screenshot
        await self.take_screenshot("step_000")

        print(f"✓ Browser ready at {url}")

    async def stop(self):
        """Stop browser"""
        if self.browser:
            await self.browser.close()
            print("🛑 Browser closed")

    async def execute_action(self, tool_name: str, **params) -> Dict[str, Any]:
        """
        Execute an action/tool call

        Args:
            tool_name: Name of tool to execute
            **params: Parameters for the tool

        Returns:
            Dict with success status and result
        """
        if not self.page:
            return {"success": False, "error": "Browser not started"}

        self.step_count += 1
        print(f"\n{'=' * 60}")
        print(f"Step {self.step_count}: {tool_name.upper()}")
        print(f"{'=' * 60}")

        result = {"success": False, "tool": tool_name, "params": params}

        try:
            if tool_name == "click":
                result = await self._action_click(params.get("selector"))

            elif tool_name == "type":
                result = await self._action_type(
                    params.get("selector"), params.get("text")
                )

            elif tool_name == "select":
                result = await self._action_select(
                    params.get("selector"), params.get("value")
                )

            elif tool_name == "get_page_info":
                result = await self._action_get_page_info()

            else:
                result = {"success": False, "error": f"Unknown tool: {tool_name}"}

            # Record action in history
            if result["success"]:
                action_str = self._format_action_for_history(tool_name, params, result)
                self.action_history.append(action_str)
                print(f"✓ {action_str}")

                # Take screenshot after successful action
                await self.take_screenshot(f"step_{self.step_count:03d}")
            else:
                print(f"✗ Failed: {result.get('error', 'Unknown error')}")

        except Exception as e:
            result = {
                "success": False,
                "error": str(e),
                "tool": tool_name,
                "params": params,
            }
            print(f"✗ Exception: {e}")

        return result

    async def _action_click(self, selector: str) -> Dict[str, Any]:
        """Execute click action"""
        assert self.page

        await self.page.click(selector, timeout=5000)  # TODO: click with coordinates
        await self.page.wait_for_load_state("load", timeout=5000)

        return {
            "success": True,
            "tool": "click",
            "selector": selector,
            "url_after": self.page.url,
        }

    async def _action_type(self, selector: str, text: str) -> Dict[str, Any]:
        """Execute type action"""
        assert self.page

        await self.page.fill(selector, text, timeout=5000)

        # Press Enter
        await self.page.press(selector, "Enter")

        # Wait for potential navigation
        try:
            await self.page.wait_for_load_state("load", timeout=5000)
        except:
            pass  # Page might not navigate, that's okay

        return {
            "success": True,
            "tool": "type",
            "selector": selector,
            "text": text,
            "pressed_enter": True,
        }

    async def _action_select(self, selector: str, value: str) -> Dict[str, Any]:
        """Execute select action"""
        await self.page.select_option(selector, value, timeout=5000)

        return {"success": True, "tool": "select", "selector": selector, "value": value}

    async def _action_get_page_info(self) -> Dict[str, Any]:
        """Get current page information"""
        return {
            "success": True,
            "tool": "get_page_info",
            "url": self.page.url,
            "title": await self.page.title(),
        }

    def _format_action_for_history(
        self, tool_name: str, params: Dict, result: Dict
    ) -> str:
        """Format action for history in Mind2Web style"""
        selector = params.get("selector", "")

        if tool_name == "click":
            return f"<{selector}> -> CLICK"
        elif tool_name == "type":
            text = params.get("text", "")
            return f"<{selector}> -> TYPE: {text}"
        elif tool_name == "select":
            value = params.get("value", "")
            return f"<{selector}> -> SELECT: {value}"
        else:
            return f"{tool_name}: {params}"

    async def take_screenshot(self, name: str | None = None) -> str:
        """
        Take screenshot and save it

        Returns:
            Path to saved screenshot
        """
        if not self.page:
            return ""

        if name is None:
            name = f"screenshot_{len(self.screenshots):03d}"

        screenshot_path = (
            self.output_dir / TASK_RESULT_SCREENSHOTS_FOLDER / f"{name}.png"
        )
        await self.page.screenshot(path=str(screenshot_path), full_page=True)

        self.screenshots.append(str(screenshot_path))
        print(f"📸 Screenshot saved: {screenshot_path}")

        return str(screenshot_path)

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

    async def get_html(self, cleaned: bool = True, format: str = "html") -> str:
        """Get current page HTML"""
        if not self.page:
            return ""

        raw_html = await self.page.content()

        if not cleaned:
            return raw_html

        if format == "text":
            self.html_cleaner.clean_to_text_tree(raw_html)

        return self.html_cleaner.clean(raw_html)

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
                "final_url": self.page.url if self.page else "",
            },
        }

        output_file = self.output_dir / f"{TASK_RESULT_FILE_NAME}.json"
        with open(output_file, "w") as f:
            json.dump(session_data, f, indent=2)

        print(f"\n💾 Session saved to: {output_file}")
        return session_data


# Example usage and testing
async def demo_basic_usage():
    """Demo: Basic browser automation"""
    agent = BrowserAgent(headless=False, output_dir="./output/demo_output")

    try:
        # Start browser
        await agent.start("https://www.google.com")

        # Execute actions
        await agent.execute_action(
            "type", selector="textarea[name='q']", text="Playwright Python"
        )

        await agent.execute_action("click", selector="input[name='btnK']")

        # Wait a bit for results
        await asyncio.sleep(2)

        # Get page info
        info = await agent.execute_action("get_page_info")
        print(f"\nCurrent page: {info.get('url')}")

        # Save session
        agent.save_session(
            task_id="demo_001",
            task_description="Search for Playwright Python on Google",
            final_response="Successfully searched and got results",
        )

        print(f"\n📊 Action History:")
        for i, action in enumerate(agent.get_action_history(), 1):
            print(f"  {i}. {action}")

    finally:
        await agent.stop()


async def demo_discogs_task():
    """Demo: Discogs submission guidelines (your example)"""
    agent = BrowserAgent(headless=False, output_dir=".output/discogs_output")

    try:
        await agent.start("https://www.discogs.com")

        # Accept cookies (adjust selector based on actual page)
        try:
            await agent.execute_action(
                "click", selector="button#onetrust-accept-btn-handler"
            )
        except:
            print("No cookie banner or different selector")

        # Navigate to help/support
        await agent.execute_action("click", selector="a[href*='support']")

        await asyncio.sleep(1)

        # Look for submission guidelines
        await agent.execute_action("click", selector="a[href*='submission-guidelines']")

        # Save session
        final_url = agent.page.url if agent.page else ""
        agent.save_session(
            task_id="fb7b4f784cfde003e2548fdf4e8d6b4f",
            task_description="Open the page with an overview of the submission of releases on Discogs.",
            final_response=f"The page with submission guidelines is open: {final_url}",
        )

        print(f"\n✓ Task completed!")
        print(f"Final URL: {final_url}")

    finally:
        await agent.stop()


async def demo_with_manual_control():
    """Demo: Interactive mode - you control the actions"""
    agent = BrowserAgent(headless=False, output_dir=".output/manual_output")

    try:
        url = input("Enter starting URL: ").strip() or "https://www.google.com"
        await agent.start(url)

        print("\n" + "=" * 60)
        print("Available tools:")
        for tool in agent.tools:
            print(f"  - {tool['name']}: {tool['description']}")
        print("=" * 60)

        while True:
            print("\nEnter command (or 'quit' to exit):")
            print("Examples:")
            print("  click button#search")
            print("  type input[name='q'] hello world")
            print("  select select#country US")
            print("  info")

            command = input("> ").strip()

            if command.lower() in ["quit", "exit", "q"]:
                break

            if not command:
                continue

            # Parse command
            parts = command.split(maxsplit=2)
            if len(parts) < 1:
                continue

            tool = parts[0]

            if tool == "click" and len(parts) >= 2:
                await agent.execute_action("click", selector=parts[1])

            elif tool == "type" and len(parts) >= 3:
                selector = parts[1]
                text = parts[2]
                await agent.execute_action("type", selector=selector, text=text)

            elif tool == "select" and len(parts) >= 3:
                selector = parts[1]
                value = parts[2]
                await agent.execute_action("select", selector=selector, value=value)

            elif tool == "info":
                result = await agent.execute_action("get_page_info")
                print(f"URL: {result.get('url')}")
                print(f"Title: {result.get('title')}")

            else:
                print(f"Unknown command: {command}")

        # Save session
        task_id = input("\nEnter task ID: ").strip() or "manual_001"
        task_desc = (
            input("Enter task description: ").strip() or "Manual browsing session"
        )

        agent.save_session(
            task_id=task_id,
            task_description=task_desc,
            final_response="Manual session completed",
        )

    finally:
        await agent.stop()


if __name__ == "__main__":
    print("Choose demo:")
    print("1. Basic Google search")
    print("2. Discogs submission guidelines")
    print("3. Manual control")

    choice = input("\nEnter choice (1-3): ").strip()

    if choice == "1":
        asyncio.run(demo_basic_usage())
    elif choice == "2":
        asyncio.run(demo_discogs_task())
    elif choice == "3":
        asyncio.run(demo_with_manual_control())
    else:
        print("Running basic demo...")
        asyncio.run(demo_basic_usage())

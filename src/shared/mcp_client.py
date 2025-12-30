"""
MCP Browser Client for Playwright MCP Server integration.

This module provides a Python client for the Playwright MCP Server,
enabling browser automation via the Model Context Protocol.
"""

import asyncio
import json
import logging
import subprocess
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class MCPBrowserClient:
    """
    Client for communicating with the Playwright MCP Server.

    This class manages the lifecycle of an MCP server subprocess and provides
    methods for browser automation via MCP tools using the Model Context Protocol.

    The client uses dynamic tool discovery - all browser automation capabilities
    are discovered at runtime from the MCP server, making the integration
    future-proof against server API changes.

    Attributes:
        server_process: The MCP server subprocess (initialized in start())
        _message_id: Counter for JSON-RPC message IDs (increments with each request)
        _initialized: Flag indicating if MCP handshake is complete
        _server_info: Server capabilities from initialize response
        _tools_cache: Cached list of available tools from tools/list
        _tools_by_name: Dictionary mapping tool names to schemas for O(1) lookup

    Example:
        >>> client = MCPBrowserClient()
        >>> await client.start()  # Launches MCP server and discovers tools
        >>> tools = await client.list_tools()  # Get available tools
        >>> await client.call_tool("browser_navigate", url="https://example.com")
        >>> await client.call_tool("browser_click", ref="s12")
        >>> await client.stop()  # Clean shutdown
    """

    def __init__(self):
        """
        Initialize the MCP browser client.

        Sets up all internal state for MCP communication. The MCP server
        subprocess is not started until start() is called.

        After initialization, the client is ready to call start(), which will:
        - Launch the MCP server subprocess
        - Perform protocol handshake
        - Discover available tools
        """
        self.server_process: Optional[subprocess.Popen] = None
        self._message_id: int = 0
        self._initialized: bool = False
        self._server_info: Optional[Dict[str, Any]] = None
        self._tools_cache: Optional[List[Dict[str, Any]]] = None
        self._tools_by_name: Dict[str, Dict[str, Any]] = {}
        logger.info("MCPBrowserClient initialized")

    async def start(self) -> None:
        """
        Start the MCP server subprocess.

        This method will launch the Playwright MCP Server as a subprocess
        and establish communication channels via stdin/stdout pipes.

        The server is launched with:
        - Chromium browser in headless mode
        - No sandbox (required for Docker)
        - JSON-RPC communication via stdio

        After subprocess launch, performs MCP protocol handshake and
        discovers available tools automatically.

        Raises:
            RuntimeError: If server fails to start, handshake fails, or
                         server process exits prematurely

        Example:
            >>> client = MCPBrowserClient()
            >>> await client.start()  # Server now running, tools discovered
        """
        if self.server_process is not None:
            logger.warning("MCP server already running")
            return

        logger.info("Starting MCP server subprocess")
        try:
            # Launch MCP server via npx
            # Use chromium browser installed via 'npx playwright install chromium' in Dockerfile
            # The MCP server will find the browser automatically in its default location
            self.server_process = subprocess.Popen(
                [
                    "npx",
                    "-y",
                    "@playwright/mcp",
                    "--browser",
                    "chromium",
                    "--headless",  # Run in headless mode for Docker
                    "--no-sandbox",  # Required when running as root in Docker
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            # Give the server a moment to start
            await asyncio.sleep(0.5)

            # Check if process started successfully
            if self.server_process.poll() is not None:
                stderr = (
                    self.server_process.stderr.read().decode()
                    if self.server_process.stderr
                    else ""
                )
                raise RuntimeError(f"MCP server failed to start: {stderr}")

            logger.info(f"MCP server started with PID {self.server_process.pid}")

            # Perform MCP initialization handshake
            await self._initialize()
        except Exception as e:
            logger.error(f"Failed to start MCP server: {e}")
            self.server_process = None
            raise RuntimeError(f"MCP server startup failed: {e}") from e

    async def stop(self) -> None:
        """
        Stop the MCP server subprocess and clean up resources.

        This method ensures proper cleanup of the server process and
        any associated resources using graceful shutdown with fallback:

        1. Send SIGTERM (graceful termination)
        2. Wait up to 5 seconds for process to exit
        3. Force kill with SIGKILL if still running
        4. Clear internal state

        Safe to call multiple times (idempotent).

        Example:
            >>> await client.stop()  # Server stopped, resources cleaned
        """
        if self.server_process is None:
            logger.warning("No MCP server to stop")
            return

        logger.info("Stopping MCP server subprocess")
        try:
            # Terminate the process gracefully
            self.server_process.terminate()

            # Wait up to 5 seconds for graceful shutdown
            for _ in range(10):
                if self.server_process.poll() is not None:
                    break
                await asyncio.sleep(0.5)

            # Force kill if still running
            if self.server_process.poll() is None:
                logger.warning("MCP server did not terminate gracefully, forcing kill")
                self.server_process.kill()
                self.server_process.wait()

            logger.info("MCP server stopped")
        except Exception as e:
            logger.error(f"Error stopping MCP server: {e}")
        finally:
            self.server_process = None

    async def _read_response(self, timeout: float = 5.0) -> Dict[str, Any]:
        """
        Read and parse a JSON-RPC response from the server with timeout.

        Args:
            timeout: Maximum seconds to wait for response (default: 5.0)

        Returns:
            Parsed JSON response as dictionary

        Raises:
            RuntimeError: If timeout occurs, response is empty, or invalid JSON
        """
        if self.server_process is None:
            raise RuntimeError("MCP server is not running")

        try:
            # Read response line with timeout
            response_line = await asyncio.wait_for(
                asyncio.to_thread(self.server_process.stdout.readline), timeout=timeout
            )
            response_text = response_line.decode().strip()

            if not response_text:
                raise RuntimeError("MCP server returned empty response")

            # Parse JSON response
            response = json.loads(response_text)
            logger.debug(f"Received response: {response}")
            return response

        except asyncio.TimeoutError:
            raise RuntimeError(f"MCP server response timeout after {timeout}s")
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Invalid JSON response from MCP server: {e}")

    async def _initialize(self) -> None:
        """
        Perform MCP initialization handshake per protocol spec.

        Implements the MCP protocol handshake (version 2024-11-05):
        1. Send 'initialize' request with client info and capabilities
        2. Receive server capabilities and version info
        3. Send 'notifications/initialized' to complete handshake
        4. Discover available tools via tools/list

        After successful handshake, sets _initialized=True and populates
        _server_info with server capabilities.

        Raises:
            RuntimeError: If server not running, handshake fails, or
                         server returns error response
        """
        if self.server_process is None:
            raise RuntimeError("Cannot initialize: server process not running")

        logger.info("Starting MCP initialization handshake")

        # Generate message ID for initialize request
        self._message_id += 1
        msg_id = self._message_id

        # Construct initialize request per MCP protocol
        initialize_request = {
            "jsonrpc": "2.0",
            "id": msg_id,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "wabe-mcp-client", "version": "0.1.0"},
            },
        }

        # Send initialize request
        request_json = json.dumps(initialize_request) + "\n"
        self.server_process.stdin.write(request_json.encode())
        self.server_process.stdin.flush()
        logger.debug(f"Sent initialize request: {initialize_request}")

        # Read initialize response with timeout
        response = await self._read_response()

        # Check for errors
        if "error" in response:
            error_msg = response["error"].get("message", "Unknown error")
            raise RuntimeError(f"MCP initialization failed: {error_msg}")

        # Store server info and capabilities
        self._server_info = response.get("result", {})
        logger.info(
            f"MCP server capabilities: {self._server_info.get('capabilities', {})}"
        )

        # Send initialized notification to complete handshake
        initialized_notification = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
        }

        notification_json = json.dumps(initialized_notification) + "\n"
        self.server_process.stdin.write(notification_json.encode())
        self.server_process.stdin.flush()
        logger.debug(f"Sent initialized notification: {initialized_notification}")

        # Mark as initialized
        self._initialized = True
        logger.info("MCP initialization handshake complete")

        # Discover available tools
        await self.list_tools()

    async def _call_tool(
        self, tool_name: str, arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Call an MCP tool via JSON-RPC.

        Args:
            tool_name: Name of the MCP tool to call (e.g., "browser_navigate")
            arguments: Dictionary of arguments to pass to the tool

        Returns:
            Dictionary containing the tool response

        Raises:
            RuntimeError: If server is not running or communication fails
        """
        if self.server_process is None:
            raise RuntimeError("MCP server is not running")

        # Generate unique message ID
        self._message_id += 1
        msg_id = self._message_id

        # Construct JSON-RPC request
        request = {
            "jsonrpc": "2.0",
            "id": msg_id,
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
        }

        # Send request to server
        request_json = json.dumps(request) + "\n"
        self.server_process.stdin.write(request_json.encode())
        self.server_process.stdin.flush()
        logger.debug(f"Sent JSON-RPC request: {request}")

        # Read response from server with timeout (30s for browser operations)
        response = await self._read_response(timeout=30.0)

        # Check for JSON-RPC error
        if "error" in response:
            error_msg = response["error"].get("message", "Unknown error")
            raise RuntimeError(f"MCP tool call failed: {error_msg}")

        return response.get("result", {})

    async def list_tools(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """
        Discover available MCP tools via tools/list request.

        This method queries the MCP server for available tools and caches
        the results for fast lookup. Tools are indexed by name in _tools_by_name.

        Args:
            force_refresh: If True, bypass cache and query server again

        Returns:
            List of tool definitions with schemas

        Raises:
            RuntimeError: If server is not running or request fails
        """
        # Return cached tools if available
        if self._tools_cache is not None and not force_refresh:
            logger.debug(f"Returning {len(self._tools_cache)} cached tools")
            return self._tools_cache

        if self.server_process is None:
            raise RuntimeError("MCP server is not running")

        logger.info("Discovering MCP tools via tools/list")

        # Generate message ID
        self._message_id += 1
        msg_id = self._message_id

        # Construct tools/list request
        request = {"jsonrpc": "2.0", "id": msg_id, "method": "tools/list", "params": {}}

        # Send request
        request_json = json.dumps(request) + "\n"
        self.server_process.stdin.write(request_json.encode())
        self.server_process.stdin.flush()
        logger.debug(f"Sent tools/list request: {request}")

        # Read response
        response = await self._read_response()

        # Check for errors
        if "error" in response:
            error_msg = response["error"].get("message", "Unknown error")
            raise RuntimeError(f"MCP tools/list failed: {error_msg}")

        # Extract tools array from result
        result = response.get("result", {})
        tools = result.get("tools", [])

        # Cache tools
        self._tools_cache = tools
        self._tools_by_name = {tool["name"]: tool for tool in tools}

        tool_names = [tool["name"] for tool in tools]
        logger.info(f"Discovered {len(tools)} MCP tools: {tool_names}")

        return tools

    def get_tool_schema(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """
        Get JSON Schema for a specific tool by name.

        Args:
            tool_name: Name of the tool to look up

        Returns:
            Tool schema dictionary if found, None otherwise

        Example:
            schema = client.get_tool_schema("browser_navigate")
            if schema:
                print(schema.get("inputSchema"))
        """
        if not self._tools_by_name:
            logger.warning("Tools not yet cached, call list_tools() first")
            return None
        return self._tools_by_name.get(tool_name)

    def _validate_arguments(
        self, tool_name: str, arguments: Dict[str, Any]
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate arguments against the tool's JSON Schema.

        Args:
            tool_name: Name of the tool to validate arguments for
            arguments: Dictionary of argument names to values

        Returns:
            Tuple of (is_valid, error_message)
            - (True, None) if arguments are valid
            - (False, error_message) if validation fails

        Example:
            is_valid, error = client._validate_arguments("browser_navigate", {"url": "https://example.com"})
            if not is_valid:
                print(f"Validation error: {error}")
        """
        # Check if tool exists in cache
        tool_schema = self.get_tool_schema(tool_name)
        if tool_schema is None:
            return False, f"Tool '{tool_name}' not found in cache"

        # Get inputSchema from tool
        input_schema = tool_schema.get("inputSchema", {})
        required_fields = input_schema.get("required", [])
        properties = input_schema.get("properties", {})

        # Validate required fields are present
        for field in required_fields:
            if field not in arguments:
                return False, f"Missing required field: '{field}'"

        # Validate parameter types match JSON Schema
        for arg_name, arg_value in arguments.items():
            if arg_name not in properties:
                # Allow extra arguments (flexible validation)
                logger.debug(f"Argument '{arg_name}' not in schema, allowing")
                continue

            prop_schema = properties[arg_name]
            expected_type = prop_schema.get("type")

            if expected_type:
                # Map JSON Schema types to Python types
                type_map = {
                    "string": str,
                    "number": (int, float),
                    "integer": int,
                    "boolean": bool,
                    "array": list,
                    "object": dict,
                }

                python_type = type_map.get(expected_type)
                if python_type and not isinstance(arg_value, python_type):
                    return (
                        False,
                        f"Type mismatch for '{arg_name}': expected {expected_type}, got {type(arg_value).__name__}",
                    )

        return True, None

    async def call_tool(self, tool_name: str, **kwargs) -> Dict[str, Any]:
        """
        Call an MCP tool with dynamic parameter validation.

        This is the main public interface for calling any MCP tool. It validates
        parameters against the tool's JSON Schema before sending the request.

        Args:
            tool_name: Name of the MCP tool to call (e.g., "browser_navigate")
            **kwargs: Tool-specific parameters as keyword arguments

        Returns:
            Dict containing the tool's response data

        Raises:
            RuntimeError: If client not initialized, validation fails, or tool call fails

        Example:
            await client.call_tool("browser_navigate", url="https://example.com")
            await client.call_tool("browser_click", ref="s12")
        """
        if not self._initialized:
            raise RuntimeError(
                "Client must be initialized before calling tools. Call start() first."
            )

        # Validate arguments against tool schema
        is_valid, error_msg = self._validate_arguments(tool_name, kwargs)
        if not is_valid:
            raise RuntimeError(f"Validation failed for '{tool_name}': {error_msg}")

        logger.info(f"Calling tool '{tool_name}' with args: {kwargs}")
        return await self._call_tool(tool_name, kwargs)

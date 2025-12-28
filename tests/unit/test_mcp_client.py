"""Unit tests for MCPBrowserClient."""

import asyncio
import json
import subprocess
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shared.mcp_client import MCPBrowserClient


@pytest.fixture
def mock_process():
    """Create a mock subprocess for MCP server."""
    process = MagicMock(spec=subprocess.Popen)
    process.poll.return_value = None  # Process is running
    process.pid = 12345
    process.stdin = MagicMock()
    process.stdout = MagicMock()
    process.stderr = MagicMock()
    return process


@pytest.fixture
def client():
    """Create an MCPBrowserClient instance."""
    return MCPBrowserClient()


class TestMCPBrowserClientLifecycle:
    """Test MCP client lifecycle methods."""

    @pytest.mark.asyncio
    async def test_initialization(self, client):
        """Test client initializes with correct attributes."""
        assert client.server_process is None
        assert client._message_id == 0
        assert client._initialized is False
        assert client._server_info is None
        assert client._tools_cache is None
        assert client._tools_by_name == {}

    @pytest.mark.asyncio
    async def test_start_launches_server(self, client, mock_process):
        """Test start() launches MCP server subprocess."""
        with patch("subprocess.Popen", return_value=mock_process):
            with patch.object(client, "_initialize", new_callable=AsyncMock):
                await client.start()

                assert client.server_process == mock_process
                # Verify subprocess was called with correct command
                subprocess.Popen.assert_called_once()
                call_args = subprocess.Popen.call_args[0][0]
                assert call_args == [
                    "npx",
                    "-y",
                    "@playwright/mcp",
                    "--browser",
                    "chromium",
                    "--headless",
                    "--no-sandbox",
                ]

    @pytest.mark.asyncio
    async def test_start_fails_if_server_exits_early(self, client):
        """Test start() raises error if server process exits immediately."""
        mock_process = MagicMock(spec=subprocess.Popen)
        mock_process.poll.return_value = 1  # Process exited
        mock_stderr = MagicMock()
        mock_stderr.read.return_value = b"Server error"
        mock_process.stderr = mock_stderr

        with patch("subprocess.Popen", return_value=mock_process):
            with pytest.raises(RuntimeError, match="MCP server failed to start"):
                await client.start()

    @pytest.mark.asyncio
    async def test_stop_terminates_server(self, client, mock_process):
        """Test stop() terminates server process."""
        client.server_process = mock_process
        mock_process.poll.side_effect = [None, 0]  # Running, then stopped

        await client.stop()

        mock_process.terminate.assert_called_once()
        assert client.server_process is None

    @pytest.mark.asyncio
    async def test_stop_force_kills_if_needed(self, client, mock_process):
        """Test stop() force kills server if graceful shutdown fails."""
        client.server_process = mock_process
        # Process stays running for all poll checks, then returns 0 after kill
        mock_process.poll.side_effect = [None] * 11 + [0]

        await client.stop()

        mock_process.terminate.assert_called_once()
        mock_process.kill.assert_called_once()


class TestMCPBrowserClientToolDiscovery:
    """Test MCP tool discovery methods."""

    @pytest.mark.asyncio
    async def test_list_tools_discovers_and_caches(self, client, mock_process):
        """Test list_tools() discovers tools and caches results."""
        client.server_process = mock_process

        # Mock response from MCP server
        tools_response = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "tools": [
                    {
                        "name": "browser_navigate",
                        "description": "Navigate to URL",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"url": {"type": "string"}},
                            "required": ["url"],
                        },
                    }
                ]
            },
        }

        with patch.object(
            client, "_read_response", return_value=tools_response
        ) as mock_read:
            tools = await client.list_tools()

            assert len(tools) == 1
            assert tools[0]["name"] == "browser_navigate"
            assert client._tools_cache == tools
            assert "browser_navigate" in client._tools_by_name
            mock_read.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_tools_returns_cached(self, client):
        """Test list_tools() returns cached results without server call."""
        cached_tools = [{"name": "test_tool"}]
        client._tools_cache = cached_tools

        tools = await client.list_tools()

        assert tools == cached_tools

    def test_get_tool_schema_returns_schema(self, client):
        """Test get_tool_schema() returns tool schema by name."""
        tool_schema = {"name": "browser_click", "inputSchema": {}}
        client._tools_by_name = {"browser_click": tool_schema}

        schema = client.get_tool_schema("browser_click")

        assert schema == tool_schema

    def test_get_tool_schema_returns_none_if_not_found(self, client):
        """Test get_tool_schema() returns None for unknown tool."""
        client._tools_by_name = {}

        schema = client.get_tool_schema("unknown_tool")

        assert schema is None


class TestMCPBrowserClientValidation:
    """Test parameter validation methods."""

    def test_validate_arguments_accepts_valid_args(self, client):
        """Test validation passes for valid arguments."""
        client._tools_by_name = {
            "browser_navigate": {
                "name": "browser_navigate",
                "inputSchema": {
                    "type": "object",
                    "properties": {"url": {"type": "string"}},
                    "required": ["url"],
                },
            }
        }

        is_valid, error = client._validate_arguments(
            "browser_navigate", {"url": "https://example.com"}
        )

        assert is_valid is True
        assert error is None

    def test_validate_arguments_rejects_missing_required(self, client):
        """Test validation fails for missing required fields."""
        client._tools_by_name = {
            "browser_navigate": {
                "name": "browser_navigate",
                "inputSchema": {
                    "type": "object",
                    "properties": {"url": {"type": "string"}},
                    "required": ["url"],
                },
            }
        }

        is_valid, error = client._validate_arguments("browser_navigate", {})

        assert is_valid is False
        assert "Missing required field" in error

    def test_validate_arguments_rejects_wrong_type(self, client):
        """Test validation fails for incorrect parameter types."""
        client._tools_by_name = {
            "browser_navigate": {
                "name": "browser_navigate",
                "inputSchema": {
                    "type": "object",
                    "properties": {"url": {"type": "string"}},
                    "required": ["url"],
                },
            }
        }

        is_valid, error = client._validate_arguments("browser_navigate", {"url": 123})

        assert is_valid is False
        assert "Type mismatch" in error


class TestMCPBrowserClientToolCalls:
    """Test MCP tool calling methods."""

    @pytest.mark.asyncio
    async def test_call_tool_validates_and_calls(self, client, mock_process):
        """Test call_tool() validates parameters and calls _call_tool."""
        client.server_process = mock_process
        client._initialized = True
        client._tools_by_name = {
            "browser_navigate": {
                "name": "browser_navigate",
                "inputSchema": {
                    "type": "object",
                    "properties": {"url": {"type": "string"}},
                    "required": ["url"],
                },
            }
        }

        expected_result = {"success": True}
        with patch.object(
            client, "_call_tool", return_value=expected_result
        ) as mock_call:
            result = await client.call_tool(
                "browser_navigate", url="https://example.com"
            )

            assert result == expected_result
            mock_call.assert_called_once_with(
                "browser_navigate", {"url": "https://example.com"}
            )

    @pytest.mark.asyncio
    async def test_call_tool_raises_if_not_initialized(self, client):
        """Test call_tool() raises error if client not initialized."""
        client._initialized = False

        with pytest.raises(RuntimeError, match="must be initialized"):
            await client.call_tool("browser_navigate", url="https://example.com")

    @pytest.mark.asyncio
    async def test_call_tool_raises_on_validation_error(self, client):
        """Test call_tool() raises error on validation failure."""
        client._initialized = True
        client._tools_by_name = {
            "browser_navigate": {
                "name": "browser_navigate",
                "inputSchema": {
                    "type": "object",
                    "properties": {"url": {"type": "string"}},
                    "required": ["url"],
                },
            }
        }

        with pytest.raises(RuntimeError, match="Validation failed"):
            await client.call_tool("browser_navigate")  # Missing required url

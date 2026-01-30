"""
Unit tests for ReliabilityAgent.

Tests the deterministic replay agent's helper methods and class structure.
"""

from unittest.mock import MagicMock

import pytest
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.genai import types
from pydantic import ValidationError

from scenarios.web_browser.agents.reliability import ReliabilityAgent


class TestReliabilityAgentType:
    """Tests for ReliabilityAgent class structure and fields."""

    def test_agent_has_required_fields(self):
        """Agent instance has name, description, actions."""
        agent = ReliabilityAgent()
        assert hasattr(agent, "name")
        assert hasattr(agent, "description")
        assert hasattr(agent, "actions")
        assert isinstance(agent.name, str)
        assert isinstance(agent.description, str)
        assert isinstance(agent.actions, list)

    def test_agent_name_default(self):
        """Name defaults to 'reliability_agent'."""
        agent = ReliabilityAgent()
        assert agent.name == "reliability_agent"

    def test_agent_actions_is_list(self):
        """Actions field is a list of dicts."""
        agent = ReliabilityAgent()
        assert isinstance(agent.actions, list)
        assert len(agent.actions) == 7
        for action in agent.actions:
            assert isinstance(action, dict)

    def test_agent_actions_structure(self):
        """Each action has element_pattern, tool, thought, params_template."""
        agent = ReliabilityAgent()
        for action in agent.actions[:-1]:  # All but last (which has None pattern)
            assert "element_pattern" in action
            assert "tool" in action
            assert "thought" in action
            assert "params_template" in action

    def test_agent_subclasses_base_agent(self):
        """Inherits from google.adk.agents.BaseAgent."""
        from google.adk.agents import BaseAgent

        agent = ReliabilityAgent()
        assert isinstance(agent, BaseAgent)

    def test_agent_forbids_extra_fields(self):
        """Extra fields rejected (Pydantic extra='forbid')."""
        with pytest.raises(ValidationError):
            ReliabilityAgent(foo="bar")


class TestGetStepIndex:
    """Tests for _get_step_index method."""

    def test_step_index_zero_no_prior_events(self):
        """First invocation with empty session."""
        agent = ReliabilityAgent()

        # Mock context with empty events
        ctx = MagicMock(spec=InvocationContext)
        ctx.session = MagicMock()
        ctx.session.events = []

        assert agent._get_step_index(ctx) == 0

    def test_step_index_one_after_one_event(self):
        """One prior model event by this agent."""
        agent = ReliabilityAgent()

        # Mock event by this agent
        event = MagicMock(spec=Event)
        event.author = "reliability_agent"

        ctx = MagicMock(spec=InvocationContext)
        ctx.session = MagicMock()
        ctx.session.events = [event]

        assert agent._get_step_index(ctx) == 1

    def test_step_index_six_after_six_events(self):
        """Six prior model events."""
        agent = ReliabilityAgent()

        # Mock 6 events by this agent
        events = [MagicMock(spec=Event) for _ in range(6)]
        for event in events:
            event.author = "reliability_agent"

        ctx = MagicMock(spec=InvocationContext)
        ctx.session = MagicMock()
        ctx.session.events = events

        assert agent._get_step_index(ctx) == 6

    def test_step_index_ignores_other_authors(self):
        """Events from other authors not counted."""
        agent = ReliabilityAgent()

        # Mock 3 events, only 1 by this agent
        event1 = MagicMock(spec=Event)
        event1.author = "other_agent"

        event2 = MagicMock(spec=Event)
        event2.author = "reliability_agent"

        event3 = MagicMock(spec=Event)
        event3.author = "another_agent"

        ctx = MagicMock(spec=InvocationContext)
        ctx.session = MagicMock()
        ctx.session.events = [event1, event2, event3]

        assert agent._get_step_index(ctx) == 1

    def test_step_index_empty_events_list(self):
        """Session with empty events list."""
        agent = ReliabilityAgent()

        ctx = MagicMock(spec=InvocationContext)
        ctx.session = MagicMock()
        ctx.session.events = []

        assert agent._get_step_index(ctx) == 0


class TestExtractRef:
    """Tests for _extract_ref method."""

    def test_extract_ref_found(self):
        """Pattern matches element in snapshot."""
        agent = ReliabilityAgent()
        snapshot = """
        Button: Godkänn alla kakor [ref=s42]
        Link: Click here [ref=s43]
        """

        ref = agent._extract_ref(snapshot, r"Godkänn alla kakor")
        assert ref == "s42"

    def test_extract_ref_not_found(self):
        """Pattern does not match any element."""
        agent = ReliabilityAgent()
        snapshot = """
        Button: Accept cookies [ref=s42]
        Link: Click here [ref=s43]
        """

        ref = agent._extract_ref(snapshot, r"Godkänn alla kakor")
        assert ref is None

    def test_extract_ref_empty_snapshot(self):
        """Empty snapshot text."""
        agent = ReliabilityAgent()
        ref = agent._extract_ref("", r"Godkänn alla kakor")
        assert ref is None

    def test_extract_ref_multiple_matches(self):
        """Pattern matches multiple elements, returns first."""
        agent = ReliabilityAgent()
        snapshot = """
        Button: Godkänn alla kakor [ref=s42]
        Button: Godkänn alla kakor [ref=s99]
        """

        ref = agent._extract_ref(snapshot, r"Godkänn alla kakor")
        assert ref == "s42"

    def test_extract_ref_complex_pattern(self):
        """Regex special chars in pattern."""
        agent = ReliabilityAgent()
        snapshot = """
        Link: T-Centralen (Stockholm) [ref=s123]
        """

        ref = agent._extract_ref(snapshot, r"T-Centralen \(Stockholm\)")
        assert ref == "s123"

    def test_extract_ref_various_ref_formats(self):
        """Ref values like s1, s99, s123."""
        agent = ReliabilityAgent()

        # Test s1
        snapshot1 = "Button: Click [ref=s1]"
        assert agent._extract_ref(snapshot1, r"Click") == "s1"

        # Test s99
        snapshot2 = "Button: Click [ref=s99]"
        assert agent._extract_ref(snapshot2, r"Click") == "s99"

        # Test s123
        snapshot3 = "Button: Click [ref=s123]"
        assert agent._extract_ref(snapshot3, r"Click") == "s123"


class TestGetSnapshotText:
    """Tests for _get_snapshot_text method."""

    def test_snapshot_text_single_text_part(self):
        """Single text part in user_content."""
        agent = ReliabilityAgent()

        # Mock context with single text part
        ctx = MagicMock(spec=InvocationContext)
        text_part = MagicMock()
        text_part.text = "Snapshot content here"
        ctx.user_content = MagicMock()
        ctx.user_content.parts = [text_part]

        result = agent._get_snapshot_text(ctx)
        assert result == "Snapshot content here"

    def test_snapshot_text_multiple_parts(self):
        """Multiple text parts concatenated."""
        agent = ReliabilityAgent()

        # Mock context with multiple text parts
        ctx = MagicMock(spec=InvocationContext)
        part1 = MagicMock()
        part1.text = "Part 1 "
        part2 = MagicMock()
        part2.text = "Part 2 "
        part3 = MagicMock()
        part3.text = "Part 3"
        ctx.user_content = MagicMock()
        ctx.user_content.parts = [part1, part2, part3]

        result = agent._get_snapshot_text(ctx)
        assert result == "Part 1 Part 2 Part 3"

    def test_snapshot_text_ignores_image_parts(self):
        """Image parts filtered out."""
        agent = ReliabilityAgent()

        # Mock context with text + non-text parts
        ctx = MagicMock(spec=InvocationContext)
        text_part = MagicMock()
        text_part.text = "Text content"
        image_part = MagicMock()
        # Image part doesn't have text attribute
        delattr(image_part, "text") if hasattr(image_part, "text") else None
        ctx.user_content = MagicMock()
        ctx.user_content.parts = [text_part, image_part]

        result = agent._get_snapshot_text(ctx)
        assert result == "Text content"

    def test_snapshot_text_no_text_parts(self):
        """Only non-text parts present."""
        agent = ReliabilityAgent()

        ctx = MagicMock(spec=InvocationContext)
        image_part = MagicMock(spec=[])  # No text attribute
        ctx.user_content = MagicMock()
        ctx.user_content.parts = [image_part]

        result = agent._get_snapshot_text(ctx)
        assert result == ""

    def test_snapshot_text_none_user_content(self):
        """user_content is None."""
        agent = ReliabilityAgent()

        ctx = MagicMock(spec=InvocationContext)
        ctx.user_content = None

        result = agent._get_snapshot_text(ctx)
        assert result == ""


class TestBuildResponse:
    """Tests for _build_response method."""

    def test_build_response_valid(self):
        """Standard response construction."""
        agent = ReliabilityAgent()

        response = agent._build_response(
            thought="click", tool="browser_click", params={"ref": "s42"}
        )

        assert response.startswith("<json>")
        assert response.endswith("</json>")
        assert '"thought": "click"' in response
        assert '"tool": "browser_click"' in response
        assert '"ref": "s42"' in response

    def test_build_response_empty_params(self):
        """Response with empty params dict."""
        agent = ReliabilityAgent()

        response = agent._build_response(
            thought="close", tool="browser_close", params={}
        )

        assert response.startswith("<json>")
        assert response.endswith("</json>")
        assert '"params": {}' in response

    def test_build_response_parseable(self):
        """Output is valid JSON inside <json> tags."""
        import json

        agent = ReliabilityAgent()

        response = agent._build_response(
            thought="test", tool="browser_click", params={"ref": "s42"}
        )

        # Extract JSON from <json>...</json> tags
        json_str = response.replace("<json>", "").replace("</json>", "")
        parsed = json.loads(json_str)

        assert parsed["thought"] == "test"
        assert parsed["tool"] == "browser_click"
        assert parsed["params"]["ref"] == "s42"

    def test_build_response_special_chars(self):
        """Thought with quotes/special chars."""
        import json

        agent = ReliabilityAgent()

        response = agent._build_response(
            thought='Test "quoted" text\nwith newline',
            tool="browser_click",
            params={"ref": "s42"},
        )

        # Verify it's valid JSON
        json_str = response.replace("<json>", "").replace("</json>", "")
        parsed = json.loads(json_str)

        assert parsed["thought"] == 'Test "quoted" text\nwith newline'


class TestRunAsyncImpl:
    """Tests for _run_async_impl method."""

    @pytest.mark.asyncio
    async def test_run_step_0_yields_event(self):
        """First step yields correct Event."""
        agent = ReliabilityAgent()

        # Mock context for step 0 (cookie consent)
        ctx = MagicMock(spec=InvocationContext)
        ctx.session = MagicMock()
        ctx.session.events = []  # No prior events, so step_index = 0
        ctx.invocation_id = "test-invocation-123"
        ctx.branch = "test-branch"

        # Mock user content with snapshot containing the cookie consent button
        text_part = MagicMock()
        text_part.text = "Button: Godkänn alla kakor [ref=s42]"
        ctx.user_content = MagicMock()
        ctx.user_content.parts = [text_part]

        # Run the agent
        events = []
        async for event in agent._run_async_impl(ctx):
            events.append(event)

        # Verify single event yielded
        assert len(events) == 1
        event = events[0]

        # Verify event properties
        assert event.invocation_id == "test-invocation-123"
        assert event.author == "reliability_agent"
        assert event.branch == "test-branch"
        assert event.content.role == "model"

        # Verify response content
        response_text = event.content.parts[0].text
        assert response_text.startswith("<json>")
        assert response_text.endswith("</json>")
        assert '"tool": "browser_click"' in response_text
        assert '"ref": "s42"' in response_text

    @pytest.mark.asyncio
    async def test_run_step_6_browser_close(self):
        """Last step (browser_close) needs no ref."""
        agent = ReliabilityAgent()

        # Mock context for step 6 (last step)
        ctx = MagicMock(spec=InvocationContext)
        ctx.session = MagicMock()
        # Mock 6 prior events to get step_index = 6
        events = [MagicMock(spec=Event) for _ in range(6)]
        for event in events:
            event.author = "reliability_agent"
        ctx.session.events = events
        ctx.invocation_id = "test-invocation-123"
        ctx.branch = "test-branch"
        ctx.user_content = MagicMock()
        ctx.user_content.parts = []  # Empty snapshot, not needed for close

        # Run the agent
        result_events = []
        async for event in agent._run_async_impl(ctx):
            result_events.append(event)

        # Verify single event yielded
        assert len(result_events) == 1
        event = result_events[0]

        # Verify response content
        response_text = event.content.parts[0].text
        assert '"tool": "browser_close"' in response_text
        # Should have empty params since no ref needed
        import json

        json_str = response_text.replace("<json>", "").replace("</json>", "")
        parsed = json.loads(json_str)
        assert parsed["params"] == {}

    @pytest.mark.asyncio
    async def test_run_event_has_correct_author(self):
        """Event.author matches agent name."""
        agent = ReliabilityAgent()

        ctx = MagicMock(spec=InvocationContext)
        ctx.session = MagicMock()
        ctx.session.events = []
        ctx.invocation_id = "test-invocation"
        ctx.branch = "test-branch"
        text_part = MagicMock()
        text_part.text = "Button: Godkänn alla kakor [ref=s1]"
        ctx.user_content = MagicMock()
        ctx.user_content.parts = [text_part]

        events = []
        async for event in agent._run_async_impl(ctx):
            events.append(event)

        assert events[0].author == agent.name

    @pytest.mark.asyncio
    async def test_run_event_has_invocation_id(self):
        """Event uses ctx.invocation_id."""
        agent = ReliabilityAgent()

        ctx = MagicMock(spec=InvocationContext)
        ctx.session = MagicMock()
        ctx.session.events = []
        ctx.invocation_id = "unique-id-456"
        ctx.branch = "test-branch"
        text_part = MagicMock()
        text_part.text = "Button: Godkänn alla kakor [ref=s1]"
        ctx.user_content = MagicMock()
        ctx.user_content.parts = [text_part]

        events = []
        async for event in agent._run_async_impl(ctx):
            events.append(event)

        assert events[0].invocation_id == "unique-id-456"

    @pytest.mark.asyncio
    async def test_run_event_has_branch(self):
        """Event uses ctx.branch."""
        agent = ReliabilityAgent()

        ctx = MagicMock(spec=InvocationContext)
        ctx.session = MagicMock()
        ctx.session.events = []
        ctx.invocation_id = "test-invocation"
        ctx.branch = "main-branch"
        text_part = MagicMock()
        text_part.text = "Button: Godkänn alla kakor [ref=s1]"
        ctx.user_content = MagicMock()
        ctx.user_content.parts = [text_part]

        events = []
        async for event in agent._run_async_impl(ctx):
            events.append(event)

        assert events[0].branch == "main-branch"

    @pytest.mark.asyncio
    async def test_run_event_content_role_model(self):
        """Event content role is 'model'."""
        agent = ReliabilityAgent()

        ctx = MagicMock(spec=InvocationContext)
        ctx.session = MagicMock()
        ctx.session.events = []
        ctx.invocation_id = "test-invocation"
        ctx.branch = "test-branch"
        text_part = MagicMock()
        text_part.text = "Button: Godkänn alla kakor [ref=s1]"
        ctx.user_content = MagicMock()
        ctx.user_content.parts = [text_part]

        events = []
        async for event in agent._run_async_impl(ctx):
            events.append(event)

        assert events[0].content.role == "model"

    @pytest.mark.asyncio
    async def test_run_event_content_has_json(self):
        """Event content text wraps in <json> tags."""
        agent = ReliabilityAgent()

        ctx = MagicMock(spec=InvocationContext)
        ctx.session = MagicMock()
        ctx.session.events = []
        ctx.invocation_id = "test-invocation"
        ctx.branch = "test-branch"
        text_part = MagicMock()
        text_part.text = "Button: Godkänn alla kakor [ref=s1]"
        ctx.user_content = MagicMock()
        ctx.user_content.parts = [text_part]

        events = []
        async for event in agent._run_async_impl(ctx):
            events.append(event)

        response_text = events[0].content.parts[0].text
        assert response_text.startswith("<json>")
        assert response_text.endswith("</json>")

    @pytest.mark.asyncio
    async def test_run_element_not_found_requests_snapshot(self):
        """Ref not found triggers snapshot request."""
        agent = ReliabilityAgent()

        # Mock context with snapshot that doesn't contain the expected element
        ctx = MagicMock(spec=InvocationContext)
        ctx.session = MagicMock()
        ctx.session.events = []
        ctx.invocation_id = "test-invocation"
        ctx.branch = "test-branch"
        text_part = MagicMock()
        text_part.text = "Button: Something else [ref=s99]"  # Wrong element
        ctx.user_content = MagicMock()
        ctx.user_content.parts = [text_part]

        events = []
        async for event in agent._run_async_impl(ctx):
            events.append(event)

        # Verify snapshot request
        response_text = events[0].content.parts[0].text
        import json

        json_str = response_text.replace("<json>", "").replace("</json>", "")
        parsed = json.loads(json_str)
        assert parsed["tool"] == "browser_snapshot"

    @pytest.mark.asyncio
    async def test_run_overflow_sends_close(self):
        """More invocations than steps triggers close."""
        agent = ReliabilityAgent()

        # Mock context at step 7 (beyond the 7 steps)
        ctx = MagicMock(spec=InvocationContext)
        ctx.session = MagicMock()
        # Mock 7 prior events to get step_index = 7 (overflow)
        events = [MagicMock(spec=Event) for _ in range(7)]
        for event in events:
            event.author = "reliability_agent"
        ctx.session.events = events
        ctx.invocation_id = "test-invocation"
        ctx.branch = "test-branch"
        ctx.user_content = MagicMock()
        ctx.user_content.parts = []

        result_events = []
        async for event in agent._run_async_impl(ctx):
            result_events.append(event)

        # Verify browser_close sent
        response_text = result_events[0].content.parts[0].text
        import json

        json_str = response_text.replace("<json>", "").replace("</json>", "")
        parsed = json.loads(json_str)
        assert parsed["tool"] == "browser_close"
        assert "All steps completed" in parsed["thought"]

    @pytest.mark.asyncio
    async def test_run_is_async_generator(self):
        """Method returns AsyncGenerator."""
        agent = ReliabilityAgent()

        ctx = MagicMock(spec=InvocationContext)
        ctx.session = MagicMock()
        ctx.session.events = []
        ctx.invocation_id = "test-invocation"
        ctx.branch = "test-branch"
        text_part = MagicMock()
        text_part.text = "Button: Godkänn alla kakor [ref=s1]"
        ctx.user_content = MagicMock()
        ctx.user_content.parts = [text_part]

        result = agent._run_async_impl(ctx)

        # Verify it's an async generator
        from collections.abc import AsyncGenerator

        assert isinstance(result, AsyncGenerator)

        # Clean up the generator
        events = []
        async for event in result:
            events.append(event)

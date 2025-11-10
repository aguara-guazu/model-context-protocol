#!/usr/bin/env python
"""
Anthropic API Client for MCP Tool Chaining Demo

This client connects to the MCP server and uses Claude Haiku 4.5
via Anthropic API to test the tool chaining functionality.
"""

import asyncio
import json
import os
import sys
from typing import Any

# Add parent directory to path to import mcp
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.types import (
    CallToolRequest,
    CallToolRequestParams,
    ChainStep,
    ChainStepOnFailure,
    ChainToolRequest,
    ChainToolRequestParams,
    Tool,
)


class AnthropicMCPClient:
    """Client that uses Anthropic API Claude to interact with MCP server."""

    def __init__(self, api_key: str, model: str = "claude-3-5-haiku-20241022"):
        """Initialize Anthropic client."""
        self.api_key = api_key
        self.model = model
        self.session: ClientSession | None = None
        self.available_tools: list[Tool] = []
        self.stdio_transport = None

    async def connect_to_server(self, server_script: str):
        """Connect to the MCP server."""
        import sys

        server_params = StdioServerParameters(
            command=sys.executable,
            args=[server_script],
            env=None,
        )

        print("🔌 Starting MCP server...")
        # Start the server and create session
        self.stdio_transport = await stdio_client(server_params).__aenter__()
        read_stream, write_stream = self.stdio_transport

        self.session = ClientSession(read_stream, write_stream)
        await self.session.__aenter__()

        # Initialize the session
        print("🔌 Connecting to MCP server...")
        init_result = await self.session.initialize()
        print(f"✅ Connected to: {init_result.serverInfo.name}")
        print(f"   Protocol version: {init_result.protocolVersion}")

        # Check if chaining is supported
        if init_result.capabilities.tools and init_result.capabilities.tools.chaining:
            print("✅ Server supports tool chaining!")
        else:
            print("⚠️  Server does not support tool chaining")

        # List available tools
        try:
            tools_result = await self.session.list_tools()
            self.available_tools = tools_result.tools
            print(f"\n📦 Available tools: {len(self.available_tools)}")
            for tool in self.available_tools:
                chainable = "✓" if tool.outputSchema else "✗"
                print(f"   [{chainable}] {tool.name}: {tool.description[:60]}...")
        except Exception as e:
            print(f"⚠️  Error listing tools: {e}")
            self.available_tools = []

        return self.stdio_transport

    def call_claude(self, prompt: str, system_prompt: str | None = None) -> str:
        """Call Claude via Anthropic API."""
        import httpx

        messages = [{"role": "user", "content": prompt}]

        request_body = {
            "model": self.model,
            "max_tokens": 4096,
            "messages": messages,
        }

        if system_prompt:
            request_body["system"] = system_prompt

        print(f"\n🤖 Calling Claude Haiku 4.5 via Anthropic API...")
        print(f"   Model: {self.model}")

        response = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json=request_body,
            timeout=60.0,
        )

        response.raise_for_status()
        response_data = response.json()
        return response_data["content"][0]["text"]

    async def test_single_tool(self):
        """Test calling a single tool."""
        print("\n" + "=" * 60)
        print("TEST 1: Single Tool Call")
        print("=" * 60)

        request = CallToolRequest(
            method="tools/call",
            params=CallToolRequestParams(
                name="fetch_user_data",
                arguments={"user_id": "user123"},
            ),
        )

        print("📤 Sending request: fetch_user_data(user_id='user123')")
        result = await self.session.send_request(request, result_type=type(None))

        print(f"📥 Result status: {'Error' if result.isError else 'Success'}")
        if result.structuredContent:
            print(f"   User: {result.structuredContent.get('name')}")
            print(f"   Bio: {result.structuredContent.get('bio')}")
            print(f"   Posts: {len(result.structuredContent.get('posts', []))}")

        return result

    async def test_simple_chain(self):
        """Test a simple two-step chain."""
        print("\n" + "=" * 60)
        print("TEST 2: Simple Tool Chain (Fetch → Analyze)")
        print("=" * 60)

        chain_request = ChainToolRequest(
            method="tools/chain",
            params=ChainToolRequestParams(
                chain=[
                    ChainStep(
                        tool="fetch_user_data",
                        id="fetch",
                        params={"user_id": "user123"},
                    ),
                    ChainStep(
                        tool="analyze_sentiment",
                        id="sentiment",
                        params={
                            "text": "fetch.bio",  # Reference the bio from previous step
                            "detailed": False,
                        },
                    ),
                ],
                returnFormat="full",
            ),
        )

        print("📤 Sending chain:")
        print("   Step 1: fetch_user_data(user_id='user123')")
        print("   Step 2: analyze_sentiment(text=fetch.bio)")

        result = await self.session.send_request(chain_request, result_type=type(None))

        print(f"\n📥 Chain Status: {result.status}")
        print(f"   Steps executed: {len(result.stepsExecuted)}")

        for step in result.stepsExecuted:
            emoji = "✅" if step.status == "success" else "❌"
            print(f"   {emoji} Step '{step.stepId}' ({step.tool}): {step.status} ({step.durationMs:.2f}ms)")

        if result.result:
            print(f"\n   Final Result:")
            print(f"      Sentiment: {result.result.get('overall_sentiment')}")
            print(f"      Confidence: {result.result.get('confidence')}")

        return result

    async def test_complex_chain(self):
        """Test a complex multi-step chain with error handling."""
        print("\n" + "=" * 60)
        print("TEST 3: Complex Chain (Fetch → Analyze → Calculate → Report)")
        print("=" * 60)

        chain_request = ChainToolRequest(
            method="tools/chain",
            params=ChainToolRequestParams(
                chain=[
                    ChainStep(
                        tool="fetch_user_data",
                        id="user",
                        params={"user_id": "user123"},
                    ),
                    ChainStep(
                        tool="analyze_sentiment",
                        id="sentiment",
                        params={"text": "user.bio", "detailed": False},
                        onFailure=ChainStepOnFailure(action="skip_and_continue"),
                    ),
                    ChainStep(
                        tool="calculate_metrics",
                        id="metrics",
                        params={"user_data": "user", "include_engagement_score": True},
                    ),
                    ChainStep(
                        tool="format_report",
                        id="report",
                        params={
                            "user_name": "user.name",
                            "sentiment": "sentiment",
                            "metrics": "metrics",
                        },
                    ),
                ],
                returnFormat="final_only",
                timeout=30.0,
            ),
        )

        print("📤 Sending complex chain:")
        print("   Step 1: fetch_user_data")
        print("   Step 2: analyze_sentiment (with skip_and_continue on failure)")
        print("   Step 3: calculate_metrics")
        print("   Step 4: format_report")

        result = await self.session.send_request(chain_request, result_type=type(None))

        print(f"\n📥 Chain Status: {result.status}")
        print(f"   Total steps: {len(result.stepsExecuted)}")

        for step in result.stepsExecuted:
            status_emoji = "✅" if step.status == "success" else "❌"
            print(f"   {status_emoji} {step.stepId}: {step.status} ({step.durationMs:.2f}ms)")

        if result.result:
            print(f"\n📄 Final Report:")
            print("-" * 60)
            report = result.result.get("report", "No report generated")
            print(report)
            print("-" * 60)

        return result

    async def test_with_claude_analysis(self):
        """Test having Claude analyze the available tools."""
        print("\n" + "=" * 60)
        print("TEST 4: Claude Analysis of Tool Chain Capabilities")
        print("=" * 60)

        # Give Claude information about available tools
        tools_info = "\n".join(
            [
                f"- {tool.name}: {tool.description} (chainable: {bool(tool.outputSchema)})"
                for tool in self.available_tools
            ]
        )

        system_prompt = f"""You are helping test an MCP server with tool chaining capabilities.

Available tools:
{tools_info}

The server supports chaining tools together using the tools/chain method."""

        user_prompt = """Analyze these tools and suggest 3 useful chains that could be created:

1. What would be a good 2-step chain?
2. What would be a good 3-step chain?
3. What would be a good 4-step chain with error handling?

For each chain, explain what it would accomplish and why it's useful."""

        claude_response = self.call_claude(user_prompt, system_prompt)

        print("\n🤖 Claude's Analysis:")
        print("-" * 60)
        print(claude_response)
        print("-" * 60)

        return claude_response

    async def run_all_tests(self):
        """Run all test scenarios."""
        print("\n" + "=" * 80)
        print("MCP TOOL CHAINING DEMO - ANTHROPIC API CLIENT")
        print("=" * 80)

        try:
            # Test 1: Single tool call
            await self.test_single_tool()

            # Test 2: Simple chain
            await self.test_simple_chain()

            # Test 3: Complex chain
            await self.test_complex_chain()

            # Test 4: Claude analysis
            await self.test_with_claude_analysis()

            print("\n" + "=" * 80)
            print("✅ ALL TESTS COMPLETED SUCCESSFULLY!")
            print("=" * 80)

        except Exception as e:
            print(f"\n❌ Error during tests: {e}")
            import traceback

            traceback.print_exc()
            raise

    async def cleanup(self):
        """Clean up resources."""
        if self.session:
            await self.session.__aexit__(None, None, None)
        if self.stdio_transport:
            await self.stdio_transport.__aexit__(None, None, None)


async def main():
    """Main entry point."""
    # API key from environment
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("❌ Error: ANTHROPIC_API_KEY environment variable not set")
        print("   Please set it with: export ANTHROPIC_API_KEY='your_key_here'")
        return

    # Get server script path
    server_script = os.path.join(os.path.dirname(__file__), "server.py")

    if not os.path.exists(server_script):
        print(f"❌ Server script not found: {server_script}")
        return

    # Create client and run tests
    client = AnthropicMCPClient(
        api_key=api_key,
        model="claude-3-5-haiku-20241022",
    )

    try:
        await client.connect_to_server(server_script)
        await client.run_all_tests()
    finally:
        await client.cleanup()


if __name__ == "__main__":
    asyncio.run(main())

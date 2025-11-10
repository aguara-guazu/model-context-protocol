#!/usr/bin/env python
"""
AWS Bedrock Client for MCP Tool Chaining Demo

This client connects to the MCP server and uses Claude via AWS Bedrock
to test the tool chaining functionality.

Requirements:
- AWS credentials configured (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION)
- boto3 installed
"""

import asyncio
import json
import os
import sys
from typing import Any

import boto3

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


class BedrockMCPClient:
    """Client that uses AWS Bedrock Claude to interact with MCP server."""

    def __init__(self, region: str = "us-east-1", model_id: str = "anthropic.claude-3-5-sonnet-20241022-v2:0"):
        """Initialize Bedrock client."""
        self.bedrock = boto3.client("bedrock-runtime", region_name=region)
        self.model_id = model_id
        self.session: ClientSession | None = None
        self.available_tools: list[Tool] = []

    async def connect_to_server(self, server_script: str):
        """Connect to the MCP server."""
        server_params = StdioServerParameters(
            command="python",
            args=[server_script],
            env=None,
        )

        # Start the server and create session
        stdio_transport = await stdio_client(server_params).__aenter__()
        read_stream, write_stream = stdio_transport

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
        tools_result = await self.session.list_tools()
        self.available_tools = tools_result.tools
        print(f"\n📦 Available tools: {len(self.available_tools)}")
        for tool in self.available_tools:
            chainable = "✓" if tool.outputSchema else "✗"
            print(f"   [{chainable}] {tool.name}: {tool.description}")

        return stdio_transport

    def call_claude(self, prompt: str, system_prompt: str | None = None) -> str:
        """Call Claude via Bedrock."""
        messages = [{"role": "user", "content": prompt}]

        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 4096,
            "messages": messages,
        }

        if system_prompt:
            request_body["system"] = system_prompt

        print(f"\n🤖 Calling Claude Sonnet 4.5 via Bedrock...")
        print(f"   Model: {self.model_id}")

        response = self.bedrock.invoke_model(
            modelId=self.model_id,
            body=json.dumps(request_body),
        )

        response_body = json.loads(response["body"].read())
        return response_body["content"][0]["text"]

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

        print(f"📥 Result: {result.content[0].text if result.content else 'No content'}")
        if result.structuredContent:
            print(f"   User: {result.structuredContent.get('name')}")
            print(f"   Bio: {result.structuredContent.get('bio')}")

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
            print(f"\n   Step '{step.stepId}' ({step.tool}):")
            print(f"      Status: {step.status}")
            print(f"      Duration: {step.durationMs:.2f}ms")
            if step.output:
                print(f"      Output keys: {list(step.output.keys())}")

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
            report = result.result.get("report", "No report generated")
            print(report)

        return result

    async def test_with_claude_orchestration(self):
        """Test having Claude decide what to chain."""
        print("\n" + "=" * 60)
        print("TEST 4: Claude-Orchestrated Chain")
        print("=" * 60)

        # Give Claude information about available tools
        tools_info = "\n".join(
            [f"- {tool.name}: {tool.description}" for tool in self.available_tools]
        )

        system_prompt = f"""You are helping test an MCP server with tool chaining capabilities.

Available tools:
{tools_info}

The server supports chaining tools together. When you identify a multi-step workflow,
you should explain which tools you would chain and why."""

        user_prompt = """I want to analyze user 'user123'. Specifically:
1. Get their profile information
2. Analyze the sentiment of their bio
3. Calculate engagement metrics
4. Generate a formatted report

How would you chain these tools together? Explain the chain you would create."""

        claude_response = self.call_claude(user_prompt, system_prompt)

        print("\n🤖 Claude's Response:")
        print(claude_response)

        return claude_response

    async def run_all_tests(self):
        """Run all test scenarios."""
        print("\n" + "=" * 80)
        print("MCP TOOL CHAINING DEMO - AWS BEDROCK CLIENT")
        print("=" * 80)

        try:
            # Test 1: Single tool call
            await self.test_single_tool()

            # Test 2: Simple chain
            await self.test_simple_chain()

            # Test 3: Complex chain
            await self.test_complex_chain()

            # Test 4: Claude orchestration
            await self.test_with_claude_orchestration()

            print("\n" + "=" * 80)
            print("✅ ALL TESTS COMPLETED SUCCESSFULLY!")
            print("=" * 80)

        except Exception as e:
            print(f"\n❌ Error during tests: {e}")
            import traceback

            traceback.print_exc()
            raise


async def main():
    """Main entry point."""
    # Check for AWS credentials
    if not os.getenv("AWS_ACCESS_KEY_ID"):
        print("⚠️  Warning: AWS_ACCESS_KEY_ID not set")
        print("   Set AWS credentials as environment variables:")
        print("   export AWS_ACCESS_KEY_ID=your_key")
        print("   export AWS_SECRET_ACCESS_KEY=your_secret")
        print("   export AWS_REGION=us-east-1")
        return

    # Get server script path
    server_script = os.path.join(os.path.dirname(__file__), "server.py")

    if not os.path.exists(server_script):
        print(f"❌ Server script not found: {server_script}")
        return

    # Create client and run tests
    client = BedrockMCPClient(
        region=os.getenv("AWS_REGION", "us-east-1"),
        model_id="anthropic.claude-3-5-sonnet-20241022-v2:0",
    )

    stdio_transport = None
    try:
        stdio_transport = await client.connect_to_server(server_script)
        await client.run_all_tests()
    finally:
        if client.session:
            await client.session.__aexit__(None, None, None)
        if stdio_transport:
            await stdio_transport.__aexit__(None, None, None)


if __name__ == "__main__":
    asyncio.run(main())

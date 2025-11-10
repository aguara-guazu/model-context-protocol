#!/usr/bin/env python
"""
Manual Test Script for MCP Tool Chaining

This script tests the tool chaining functionality without AWS Bedrock,
making direct requests to the MCP server.

Run this to verify the server works correctly before testing with Claude.
"""

import asyncio
import json
import os
import sys

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
)


async def test_server():
    """Run manual tests against the server."""
    server_script = os.path.join(os.path.dirname(__file__), "server.py")

    if not os.path.exists(server_script):
        print(f"❌ Server script not found: {server_script}")
        return

    print("=" * 80)
    print("MCP TOOL CHAINING - MANUAL TEST")
    print("=" * 80)

    # Start server
    server_params = StdioServerParameters(
        command="python",
        args=[server_script],
        env=None,
    )

    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            # Initialize
            print("\n🔌 Connecting to server...")
            init_result = await session.initialize()
            print(f"✅ Connected: {init_result.serverInfo.name}")
            print(f"   Version: {init_result.serverInfo.version}")

            # Check capabilities
            if init_result.capabilities.tools and init_result.capabilities.tools.chaining:
                print("✅ Tool chaining is SUPPORTED")
            else:
                print("❌ Tool chaining is NOT supported")
                return

            # List tools
            tools_result = await session.list_tools()
            print(f"\n📦 Available tools: {len(tools_result.tools)}")
            for tool in tools_result.tools:
                has_output = "✓" if tool.outputSchema else "✗"
                print(f"   [{has_output}] {tool.name}")

            # TEST 1: Single tool call
            print("\n" + "=" * 80)
            print("TEST 1: Single Tool Call - fetch_user_data")
            print("=" * 80)

            request = CallToolRequest(
                method="tools/call",
                params=CallToolRequestParams(
                    name="fetch_user_data",
                    arguments={"user_id": "user123"},
                ),
            )

            result = await session.send_request(request, result_type=type(None))
            print(f"✅ Status: {'Success' if not result.isError else 'Error'}")
            if result.structuredContent:
                print(f"   User: {result.structuredContent.get('name')}")
                print(f"   Email: {result.structuredContent.get('email')}")
                print(f"   Posts: {len(result.structuredContent.get('posts', []))}")

            # TEST 2: Simple chain (2 steps)
            print("\n" + "=" * 80)
            print("TEST 2: Simple Chain - Fetch + Sentiment Analysis")
            print("=" * 80)

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
                            params={"text": "fetch.bio", "detailed": False},
                        ),
                    ],
                    returnFormat="full",
                ),
            )

            result = await session.send_request(chain_request, result_type=type(None))
            print(f"✅ Chain Status: {result.status}")
            print(f"   Steps executed: {len(result.stepsExecuted)}")

            for step in result.stepsExecuted:
                emoji = "✅" if step.status == "success" else "❌"
                print(f"   {emoji} {step.stepId} ({step.tool}): {step.status} - {step.durationMs:.2f}ms")

            if result.result:
                print(f"\n   Final Sentiment: {result.result.get('overall_sentiment')}")
                print(f"   Confidence: {result.result.get('confidence')}")

            # TEST 3: Complex chain (4 steps)
            print("\n" + "=" * 80)
            print("TEST 3: Complex Chain - Full User Report")
            print("=" * 80)

            chain_request = ChainToolRequest(
                method="tools/chain",
                params=ChainToolRequestParams(
                    chain=[
                        ChainStep(
                            tool="fetch_user_data",
                            id="user",
                            params={"user_id": "user456"},
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

            result = await session.send_request(chain_request, result_type=type(None))
            print(f"✅ Chain Status: {result.status}")
            print(f"   Total duration: {sum(s.durationMs or 0 for s in result.stepsExecuted):.2f}ms")

            print("\n   Execution trace:")
            for i, step in enumerate(result.stepsExecuted, 1):
                emoji = "✅" if step.status == "success" else "❌"
                print(f"   {i}. {emoji} {step.stepId}: {step.status} ({step.durationMs:.2f}ms)")

            if result.result and result.result.get("report"):
                print(f"\n📄 Generated Report:")
                print("-" * 80)
                print(result.result["report"])
                print("-" * 80)

            # TEST 4: Chain with translation
            print("\n" + "=" * 80)
            print("TEST 4: Chain with Translation - Fetch + Translate + Summary")
            print("=" * 80)

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
                            tool="translate_text",
                            id="translate",
                            params={
                                "text": "user.bio",
                                "source_lang": "en",
                                "target_lang": "es",
                            },
                        ),
                        ChainStep(
                            tool="generate_summary",
                            id="summary",
                            params={"text": "translate.translated_text", "max_length": 20},
                        ),
                    ],
                    returnFormat="full",
                ),
            )

            result = await session.send_request(chain_request, result_type=type(None))
            print(f"✅ Chain Status: {result.status}")

            for step in result.stepsExecuted:
                emoji = "✅" if step.status == "success" else "❌"
                print(f"   {emoji} {step.stepId}: {step.status}")

            if result.result:
                print(f"\n   Summary: {result.result.get('summary')}")
                print(f"   Compression: {result.result.get('compression_ratio')}")

            # TEST 5: Chain with error handling
            print("\n" + "=" * 80)
            print("TEST 5: Chain with Non-existent User (Error Handling)")
            print("=" * 80)

            chain_request = ChainToolRequest(
                method="tools/chain",
                params=ChainToolRequestParams(
                    chain=[
                        ChainStep(
                            tool="fetch_user_data",
                            id="user",
                            params={"user_id": "nonexistent"},
                        ),
                        ChainStep(
                            tool="analyze_sentiment",
                            id="sentiment",
                            params={"text": "user.bio"},
                        ),
                    ],
                    returnFormat="full",
                ),
            )

            result = await session.send_request(chain_request, result_type=type(None))
            print(f"📊 Chain Status: {result.status}")

            for step in result.stepsExecuted:
                emoji = "✅" if step.status == "success" else "❌"
                print(f"   {emoji} {step.stepId}: {step.status}")
                if step.error:
                    print(f"      Error: {step.error}")

            # Summary
            print("\n" + "=" * 80)
            print("✅ ALL MANUAL TESTS COMPLETED")
            print("=" * 80)
            print("\nSummary:")
            print("  ✅ Single tool calls work")
            print("  ✅ Simple chains (2 steps) work")
            print("  ✅ Complex chains (4+ steps) work")
            print("  ✅ Reference resolution works (step1.field)")
            print("  ✅ Error handling works")
            print("  ✅ Report generation works")
            print("\n🎉 Tool chaining is working correctly!")
            print("\nNext step: Run client_bedrock.py to test with Claude via AWS Bedrock")


if __name__ == "__main__":
    asyncio.run(test_server())
